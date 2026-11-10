# Evaluating Condense with `sift-eval`

`sift-eval` scores Condense's two answer surfaces against a **golden question set** that you
write. It gives you numbers to compare before and after a change (chunk size, rerank strategy,
`RETRIEVE_K`, a new LLM) instead of judging the results by eye.

- **Find**: the `/search` pipeline (embed → retrieve `RETRIEVE_K` → version-collapse →
  rerank → top-`FINAL_K` + recap).
- **Ask**: the `/v1/answer` tool-calling agent.

It runs the real pipeline in-process from the same `.env` as the server, so it sees what
`/search` hides: the full ranked list, the exact passages the LLM read, and how long each stage
took. Design decisions: D73 to D75 in `docs/Quentin/DECISIONS.md`.

## 1. What it measures

| Metric | Meaning | Better | Surfaces |
|---|---|---|---|
| **recall@k** | share of the *required* gold evidence found in the top k. Alternatives (entries sharing a `group`) count once, as soon as any of them is found | ↑ | Find (exact), Ask (cited sources) |
| **complete@k** | was *all* the required evidence in the top k? Equals hit@k for a one-group question; for a multi-hop one it says whether retrieval surfaced everything the answer needs | ↑ | Find, Ask |
| **precision@k** | share of the top k that is gold evidence (÷ k) | ↑ | Find, Ask |
| **hit@k** | was *any* gold evidence in the top k? Find's **final hit@1 is the product's own question: did `/search` return the right thing?** | ↑ | Find, Ask |
| **MRR** | 1 ÷ rank of the first gold passage | ↑ | Find, Ask |
| **answer relevancy** | does the answer address the question? (RAGAS: questions generated back from the answer, compared with the real one) | ↑ | both |
| **faithfulness** | share of the answer's claims supported by the passages the generator actually saw | ↑ | both |
| **answer correctness** | agreement with your `reference` answer (RAGAS: claim-level F1 plus semantic similarity). An F1, so true details the reference doesn't list also cost points | ↑ | both |
| **answer recall** | share of the `reference`'s facts the answer states; extra details don't count against it (the reference is split into claims and each is checked against the answer, using RAGAS `FactualCorrectness`'s prompts). With references that hold only what's asked, this is the "did it answer correctly?" number. RAGAS's own recall mode isn't used: it scored correct answers 0 under a strict judge (D84) | ↑ | both |
| **context utilization** | were the passages given to the generator actually useful for its answer? (rank-weighted) | ↑ | both |
| **noise sensitivity** | share of the answer's claims that a relevant retrieved passage backs but that aren't correct (RAGAS, relevant mode). "Correct" means supported by the question plus `reference`: RAGAS checked against the bare reference, which marked correct answers wrong (D85). A true detail the reference doesn't list still counts as wrong, so with minimal references this also rises with verbosity: compare runs over the same set, don't read it as an error rate | ↓ | both |
| **noise robustness** | `--noise`: answer correctness as irrelevant passages are mixed into the recap context, and the ratio correctness@max-noise ÷ correctness@clean | ↑ | Find |
| **correct abstention** | on `answerable: false` questions: did the system say the documents don't cover it? | ↑ | both |
| **false refusal** | on answerable questions: did it wrongly decline? | ↓ | both |
| **latency** | mean / p50 / p95 / max per stage. Find: `embed`, `retrieve`, `collapse`, `rerank`, `recap`, `total`. Ask: `model`, `tools`, `total` | ↓ | both |

Retrieval metrics come at two levels:

- **doc**: the ranking is deduped by file, and a hit is the right file.
- **chunk**: the passage itself must match the gold page and evidence quote.

Find's retrieval metrics are reported at two stages:

- **retrieved**: the raw vector search, before rerank.
- **final**: after collapse and rerank.

If final scores beat retrieved scores, the reranker is earning its cost.

With one gold document per question, doc-level precision@5 can't exceed 0.2. Precision is for
comparing runs, not for comparing against 1.0.

## 2. Install and configure

```bash
pip install -e '.[eval]'        # RAGAS for the judged metrics (retrieval + latency work without it)
```

The system under test is configured exactly like the server, by the same `.env`. Use
`--env-file` to point at another one. The eval's own knobs are `EVAL_*` keys; they're listed,
commented out, at the bottom of `.env.example`. The important ones:

```bash
EVAL_JUDGE_BASE_URL=https://api.mistral.ai/v1   # any OpenAI-compatible endpoint
EVAL_JUDGE_MODEL=mistral-large-latest           # defaults to LLM_MODEL
EVAL_JUDGE_API_KEY=...
# EVAL_EMBED_*  defaults to EMBED_* (used by answer relevancy / correctness)
```

For a Claude judge, use the native SDK. Anthropic's OpenAI-compatible endpoint rejects the
JSON mode and the `temperature`/`top_p` values RAGAS sends (D82):

```bash
EVAL_JUDGE_PROVIDER=anthropic
EVAL_JUDGE_BASE_URL=https://api.anthropic.com/v1
EVAL_JUDGE_MODEL=claude-haiku-5-5
```

**Use a judge stronger than, and different from, the generator.** Models grade their own
answers generously, and the report warns when the judge and the generator are the same model.
Small local models often return output RAGAS can't parse. Those scores show up as `failed`
counts, not crashes.

## 3. Write the golden set

One JSON object per line. `#` lines are comments. Start from `evals/golden.example.jsonl`.

```json
{"id": "refunds-01",
 "question": "How long does a refund take once it's approved?",
 "reference": "Refunds are paid out within two to three business days of approval.",
 "relevant": [{"path": "policies/refunds_v2.md", "page": 1, "evidence": "two to three business days"}],
 "tags": ["policy"]}
```

| Field | Required | What it enables |
|---|---|---|
| `id` | yes | unique key, used to diff runs |
| `question` | yes | what the system is asked |
| `reference` | recommended | answer correctness and recall, noise sensitivity, the noise sweep |
| `relevant[]` | recommended | every retrieval metric. `path` is required; `page` and `evidence` make matching stricter; `group` marks alternatives (below) |
| `answerable` | no (default `true`) | `false`: the corpus doesn't cover it, so the item scores abstention instead |
| `tags` | no | per-tag breakdown in the report |

**How gold is matched:**

- `path` matches a stored path exactly, or as a `/`-bounded suffix, so `policies/refunds.md`
  matches `/Users/you/Docs/policies/refunds.md`.
- `evidence` is a short verbatim quote. It's matched ignoring case and punctuation, and it still
  counts if at least 60% of its words appear in a contiguous run, which tolerates a quote split
  across a chunk boundary.
- Gold never references chunk IDs, so **the same set keeps working after you change chunking and
  re-ingest**.

**Required evidence vs alternatives (`group`):** every `relevant` entry is *required* by
default: recall counts how many of them were found. When two files each state the answer on
their own (a technique file and the tactic file that lists it, the Enterprise and ICS copies of
one mitigation), give them the same `group` label. Recall then counts the group as found when
*any* member is found:

```json
"relevant": [
  {"path": "techniques/T0884_connection-proxy.md", "evidence": "act as an intermediary", "group": "answer"},
  {"path": "tactics/TA0101_command-and-control.md", "evidence": "T0884 Connection Proxy", "group": "answer"}
]
```

A multi-hop question keeps one group per fact it needs (or no labels at all), so finding half of
it is recall 0.5 and complete 0. Two rules keep alternatives honest, and `validate` checks them:

- **An alternative must state the answer by itself.** Give it an `evidence` quote showing where.
  An alternative without page or evidence lets any chunk of that file satisfy the group, and
  `validate` warns about it. A file that merely mentions the topic is not an alternative.
- **Labels are per item and must match exactly.** A label used by one entry only is reported
  as a likely typo.

Groups change recall and complete@k only. Precision, hit@k and MRR already counted any matching
entry, and they are unchanged. A set without labels scores exactly as before.

**What makes a good set:**

- **Size:** 50–100 questions is enough to see real differences; under 20, everything is noise.
- **Use your users' words.** Paraphrased questions are the honest test. Questions that copy the
  document's wording make retrieval look better than it is.
- **Mix the question types:**
  - single-fact;
  - multi-document (several `relevant` entries);
  - version-sensitive (an old and a new copy of a policy, with gold on the new one);
  - enumeration ("which documents mention X");
  - **10–15% unanswerable**.
- **Keep evidence quotes short:** 3 to 12 words that are actually in the document.
- **Write `reference` answers that hold exactly what the question asks**: every part it asks
  for, nothing else. Background, dates or IDs the question didn't ask about, and grading hints
  ("X also counts"), go in `notes`. The judge treats every sentence of the reference as a fact
  the answer must state.
- **Write the reference in the language the answer will come back in.** Both surfaces answer in
  the question's language, so a translated question needs a translated reference.
- **Tag questions** by topic and type, so the report shows where quality is weak. If you add
  reworded or translated copies of a question, tag each kind (`keywords`, `de`, …) and the
  originals (`base`). Then compare answer metrics within a kind, in the report's By-tag table:
  answer relevancy in particular depends on how the question is phrased, so a mean taken across
  kinds mixes phrasing with quality.

## 4. Commands

```bash
# Check every gold path/page/quote exists in the index (exit 1 on errors)
sift-eval validate --golden evals/golden.jsonl

# Have the judge LLM draft questions from your documents (never overwrites; review every one!)
sift-eval bootstrap --out evals/draft.jsonl --n 30

# A run: Find + Ask, judged, with the noise sweep
sift-eval run --golden evals/golden.jsonl --label baseline --noise

# Fast and free: retrieval + latency only, no judge calls
sift-eval run --golden evals/golden.jsonl --skip-judge --surfaces find

# Subsets
sift-eval run --golden evals/golden.jsonl --tags policy,hr --limit 20

# Re-score an existing run with a different judge (no system calls)
EVAL_JUDGE_MODEL=other-model sift-eval judge eval-runs/20261105-101500-baseline

# Re-score only some metrics; every other score (abstention too) is kept
sift-eval judge eval-runs/20261105-101500-baseline --metrics answer_recall

# What changed between two runs (▲ better / ▼ worse, direction-aware)
sift-eval compare eval-runs/<baseline> eval-runs/<candidate>
```

Drafts from `bootstrap` are tagged `bootstrap` and carry `"review": "todo"`. Each question was
written while looking at its answer, so rewrite it the way a user would ask it before trusting
any score.

Each run writes a folder in `eval-runs/` (gitignored, because reports quote your documents):

- `report.html`: a self-contained page with headline numbers and every table, plus a
  per-question drill-down (the answer and the ranking, with gold passages marked ✓).
- `summary.md` / `summary.json`: the aggregates. `compare` diffs the JSON, and warns when the
  two runs used different golden files: then the deltas mix set changes with system changes.
- `results.jsonl` / `noise.jsonl`: every raw row.
- `config.json`: git SHA, golden-set hash, judge, and the redacted settings it ran under.
- `golden.jsonl`: a copy of the golden set as it was at run time.

## 5. A tuning loop

```bash
sift-eval run --golden evals/golden.jsonl --label rerank-none
# change RERANK_STRATEGY=llm in .env
sift-eval run --golden evals/golden.jsonl --label rerank-llm
sift-eval compare eval-runs/*-rerank-none eval-runs/*-rerank-llm
```

For chunking experiments, re-ingest the corpus between runs. The golden set needs no changes.

## 6. Caveats

- **Cost:** each judged question makes roughly 15–25 judge-LLM calls per surface (answer recall
  alone is about 4), plus 2 per noise ratio. Use `--skip-judge` for retrieval-only iterations, and
  `EVAL_JUDGE_CONCURRENCY` to trade speed for rate limits.
- **Latency is measured in-process.** It excludes HTTP, auth and serialization, but it covers
  every model call. Questions run one at a time, and the first `EVAL_WARMUP` runs are discarded.
- **Citations are stripped before judging** (D76): inline markers like `(policies/shipping.md,
  p.1)`, `[1]` and `Source: [1]` lines are removed from the copy the judge sees, because RAGAS
  otherwise counts them as unsupported claims (a correct cited answer scored faithfulness 0.5,
  and the same answer uncited scored 1.0). Reports always show the answer verbatim. Set
  `EVAL_STRIP_CITATIONS=false` to judge raw answers.
- **Ask's retrieval metrics** are computed over the sources the agent's searches returned
  (doc level only), not over a ranking it chose.
- **Run against the same index the server uses**, ideally while it's idle. The eval only reads
  the store, and Ask's test conversations are never saved to your chat history.
