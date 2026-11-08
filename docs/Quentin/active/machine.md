> **Desktop WP COMPLETE on `feat/desktop-standalone`** (D60–D67), merge pending → v0.4.0 (its docs archive at that merge). This file now tracks the parallel **eval-harness** WP.

# Eval harness (`sift-eval`) — Machine Doc

> Full design + plan + implementation record. Paired with `human.md` (never one without the other).

**Status:** in-progress &nbsp;·&nbsp; **Branch:** `feat/eval-harness` &nbsp;·&nbsp; **Updated:** 2026-11-05

## 1. Overview
`sift-eval` is a CLI that scores Condense's two answer surfaces against a golden question set:
**Find** (`SearchPipeline`: embed → retrieve RETRIEVE_K → version-collapse → rerank → FINAL_K +
recap) and **Ask** (`AnswerPipeline`, the `/v1/answer` tool-calling agent). It is a separate
dev-tool app inside `src/sift/eval/` (D73), the same pattern as `agent/`. It builds the real
container from the same `.env` and drives the pipelines in-process. The product never imports it.

## 2. Design
- **Consumes:** `factory.build_container(settings, ephemeral_conversations=True)`,
  `SearchPipeline.trace/recap`, `AnswerPipeline.run`,
  `ToolRegistry.call("list_documents"|"get_document_chunks")`, `factory.build_completer`.
- **Produces:** `sift.eval` package, `sift-eval` console script, `[eval]` extra, run folders under
  `EVAL_OUTPUT_DIR` (default `eval-runs/`, gitignored).
- **Product changes (additive):**
  - `pipelines/search.py`: `SearchTrace{outcome, retrieved, ranked, context, timings_ms}`,
    `SearchPipeline.trace()` and `SearchPipeline.recap()`. `search()` is `trace().outcome`.
  - `factory.py`: the `ephemeral_conversations` kwarg and a public `build_completer`.
- **Data flow:**
  1. golden JSONL → `GoldenItem`s.
  2. **collect** runs sequentially: Find via `trace()`, Ask by draining the `AnswerEvent`s
     (`tool_result.detail` → contexts, `answer_delta` → response, `sources` → cited docs).
  3. `RunRecord` rows go to `results.jsonl`.
  4. Pure retrieval metrics plus latency stats.
  5. **judge** runs concurrently, bounded by `EVAL_JUDGE_CONCURRENCY`: the RAGAS collections
     metrics plus our abstention prompt.
  6. Optional **noise sweep** on Find's recap.
  7. `summary.json`, `summary.md` and `report.html` are written.
- **Matching (D75):** a hit matches a gold entry when its `source_path` equals the gold path or ends
  with `/`+gold path. If the gold entry has a page, the page must match. If it has evidence, the
  normalized quote must be a substring of the hit text, or else its token recall must be
  ≥ `EVAL_EVIDENCE_MATCH_THRESHOLD`. Metrics are computed at doc level (ranked list deduped by
  path) and chunk level.
- **Metrics:**
  - recall@k = required groups found in top-k ÷ groups (D78: entries sharing a `group` label
    are alternatives; unlabelled entries stand alone). complete@k = every group found.
  - precision@k = relevant items in top-k ÷ k.
  - hit@k: whether any gold entry is in the top-k.
  - MRR uses the first relevant rank.
  - Find is measured at two stages, `retrieved` (pre-rerank) and `final` (post-rerank). Ask is
    measured over cited sources at doc level.
  - RAGAS: `Faithfulness(user_input, response, retrieved_contexts)`,
    `AnswerRelevancy(user_input, response)` (LLM + embeddings),
    `AnswerCorrectness(user_input, response, reference)` (LLM + embeddings),
    `ContextUtilization(user_input, response, retrieved_contexts)`,
    `NoiseSensitivity(mode="relevant")(user_input, response, reference, retrieved_contexts)`
    (lower is better), and `FactualCorrectness(mode="recall")(response, reference)` as
    `answer_recall` (D77: required facts covered, verbosity-neutral).
  - By tag: doc hit@1 plus every judged metric per surface, so variant kinds are compared within
    their own tag.
- **Noise sweep (Find):**
  1. Gold passages are the chunks of the gold doc that match the evidence, falling back to the
     best retrieved chunk from the gold doc.
  2. Distractors are retrieved hits that match no gold entry (hard negatives), topped up with
     random chunks from other docs (seeded).
  3. For each ratio r: n_noise = round(N·r) and n_gold = max(1, N − n_noise), capped by the gold
     passages available. Passages are shuffled with a seed and fed to `SearchPipeline.recap`.
  4. The answers are scored with answer correctness and faithfulness.
     robustness = correctness@max(r) ÷ correctness@0.
- **Config keys (`EvalSettings`, `EVAL_` prefix, `.env`):**
  - judge: `JUDGE_BASE_URL` / `JUDGE_MODEL` / `JUDGE_API_KEY` (fall back to `LLM_*`),
    `JUDGE_CONCURRENCY=4`;
  - embeddings: `EMBED_BASE_URL` / `EMBED_MODEL` / `EMBED_API_KEY` (fall back to `EMBED_*`);
  - matching and noise: `K_VALUES=1,3,5,10`, `EVIDENCE_MATCH_THRESHOLD=0.6`,
    `NOISE_RATIOS=0,0.25,0.5,0.75`, `NOISE_CONTEXT_SIZE=4`;
  - run: `WARMUP=1`, `SEED=13`, `OUTPUT_DIR=eval-runs`, `TENANT=default`, `GROUNDING=strict`.
- **Dependency rule check:** `sift.eval` imports `sift.factory`, `sift.pipelines.*`, `sift.core.*`
  and `sift.config`, never `sift.adapters` or `sift.api`. Nothing in `core/`, `adapters/`,
  `pipelines/`, `api/` or `factory.py` imports `sift.eval` (asserted by
  `tests/contract/test_layering.py`). `ragas`/`openai` are imported lazily inside
  `ragas_judge.py` only.

## 3. Plan (writing-plans format)
> Checkbox tasks. TDD. Commit per task.

### Task 0: WP docs + decisions
- [x] `active/human.md` + `machine.md`, D73–D75, ROADMAP entry

### Task 1: `SearchPipeline.trace` / `recap`
**Files:** `src/sift/pipelines/search.py`, `tests/surface/test_search_trace.py`
- [x] failing tests: stages populated, timings keys, `context` = `ranked[:recap_context_k]`, empty base, recap off → `context == []`
- [x] implement; existing `test_search_pipeline.py` stays green unchanged

### Task 2: factory hooks
**Files:** `src/sift/factory.py`, `tests/surface/test_factory.py`
- [x] `ephemeral_conversations=True` → `FakeConversationStore` even with Turso configured; public `build_completer`

### Task 3: golden + matching + metrics (pure)
**Files:** `src/sift/eval/{__init__,records,golden,matching,metrics}.py`, `tests/eval/test_{golden,matching,metrics}.py`
- [x] schema + typo-safe parsing, suffix/page/evidence matching (contiguous token run), recall/precision/hit@k + MRR at doc and chunk level, latency stats

### Task 4: config + collect (Find + Ask)
**Files:** `src/sift/eval/{config,collect}.py`, `tests/eval/{conftest,test_collect}.py`
- [x] `EvalSettings` (+ placeholder ingest token so an eval-only `.env` loads), Find via `trace()`, Ask via the event stream (tool-result passages → contexts, `sources` → cited, tool vs model time), warmup, per-question error capture

### Task 5: judge protocol + RAGAS adapter
**Files:** `src/sift/eval/{judge,ragas_judge}.py`, `tests/eval/test_judge.py`
- [x] `Judge` protocol + `FakeJudge`, applicability rules (no reference → no correctness; no contexts → no faithfulness), `AbstentionCheck` (YES/NO via judge `Completer`), `RagasJudge` (collections metrics, per-metric failure → `None`, NaN → `None`), bounded-concurrency `judge_results`

### Task 6: noise sweep
**Files:** `src/sift/eval/{corpus,noise}.py`, `tests/eval/test_noise.py`
- [x] `corpus.py` (list docs / chunks via the toolbox, gold-path resolution), one gold passage per ref, hard-negative distractors from non-gold docs, seeded shuffle, actual-ratio recorded, recap via the production prompt, judged on correctness + faithfulness

### Task 7: report + CLI (run / judge / compare) + packaging
**Files:** `src/sift/eval/{report,runner,cli}.py`, `pyproject.toml`, `.gitignore`, `tests/eval/test_cli.py`
- [x] self-contained run folder (config/golden copy/results/noise/summary json+md/report.html), credential redaction by field-name suffix, `rejudge`, `compare` (direction-aware ▲/▼), `[eval]` extra + `sift-eval` script, `eval-runs/` gitignored

### Task 8: validate + bootstrap
**Files:** `src/sift/eval/{validate,bootstrap}.py`, `tests/eval/test_{validate,bootstrap}.py`
- [x] validate: path resolution (+ did-you-mean), ambiguity warning, page/evidence presence, missing reference/relevant warnings; bootstrap: seeded round-robin sampling, verbatim-evidence filter, never overwrites, output parses as a golden set

### Task 9: docs + guards
**Files:** `docs/evaluation.md`, `evals/golden.example.jsonl`, `.env.example`, `CLAUDE.md` §9, `docs/channel/from-quentin.md`, `tests/contract/test_layering.py`
- [x] user guide, example set (+ parses test), commented `EVAL_*` block (+ parity test), CLAUDE.md ownership/map, channel update 33, layering guards (product ↛ `sift.eval`, `sift.eval` ↛ adapters/api)

## 4. Test strategy
- Everything runs on the default fakes (`FakeEmbedder`, `FakeVectorStore` seeded via `upsert`,
  `NullReranker`, `FakeCompleter`, `FakeToolCompleter`) plus `FakeJudge`. No network.
- `ragas_judge` tests use `pytest.importorskip("ragas")` and check sample mapping and failure
  handling with a stubbed metric (no LLM calls). CI doesn't install `[eval]`, so they skip there.
- E2E: CLI `run --skip-judge` on a seeded fake store, asserting the files and metrics in
  `summary.json`.
- Real-stack check: a local `.env` (Ollama bge-m3 + Mistral + libSQL file), a 5-item golden set,
  then `validate` → `run` → `compare`.

## 5. Implementation log
| Date | Commit | Change |
|------|--------|--------|
| 2026-11-05 | 30dfb0f | WP opened; plan approved; D73–D75 |
| 2026-11-05 | a4f2134 | `SearchPipeline.trace()` + `recap()` |
| 2026-11-05 | be56ce7 | factory `ephemeral_conversations` + public `build_completer` |
| 2026-11-05 | 02e73a6 | golden schema, matching, retrieval metrics |
| 2026-11-05 | 6fdf994 | `EvalSettings` + collect (Find/Ask) |
| 2026-11-05 | 10170fc | `Judge` protocol, abstention, RAGAS adapter |
| 2026-11-05 | 009298c | noise-robustness sweep |
| 2026-11-05 | 33fca90 | runner, reports, CLI, validate, bootstrap, `[eval]` extra |
| 2026-11-05 | 29d8311 | user guide, example set, env block, layering guards, channel 33 |
| 2026-11-05 | c28faf7 | D76 citation stripping (found by the first real-stack run) |
| 2026-11-05 | — | **Real-stack verification** on a scratch libSQL DB (5 docs via the real ingest pipeline, `mistral-embed`, `mistral-small-latest` generator + judge): `validate` OK; `run --skip-judge` and `run --noise` complete with 0 errors and 0 judge failures; Find doc hit@1 1.0, answer correctness Find 0.82 / Ask 0.81, noise robustness 0.88; v2 refund policy correctly preferred over v1; unanswerable question abstained on both surfaces. ~5.7 min for 6 questions + sweep at judge concurrency 2 |
| 2026-11-07 | 54d618b | D77 `answer_recall` metric; By-tag table carries every judged metric; AnswerCorrectness skipped (not crashed) without embeddings; guide: minimal references, reference in the answer's language, compare variants per tag. Found by the MITRE silver-set audit |
| 2026-11-07 | fd401e5 | D78 alternative gold groups: `GoldRef.group`, `ref_groups`, recall over groups + `complete@k`, one noise passage per group, `validate` warns on loose alternatives / lone labels, `compare` warns on golden-set change, C@k columns in the retrieval table |
| 2026-11-07 | 7119f9f | D79 `OpenAICompatCompleter._post` retries 429/502/503/504 (exponential 2→32 s, numeric `Retry-After` honoured, 500 never retried); RAGAS judge client `max_retries=10`. Found by the first MITRE run (2,298 files, 7,278 chunks): `validate` OK, then Mistral 429s errored ~half of Find questions and would have silently truncated Ask answers |
| 2026-11-07 | 5e39daa | D80 RAGAS judge `llm_factory(..., max_tokens=4096)`: the base MITRE run's judge logged `IncompleteOutputException` (max_tokens) on faithfulness, answer correctness/recall and noise sensitivity |
| 2026-11-07 | — | **First MITRE eval** (silver set, 332 items; `condense_test_mitre/mitre.db`; bge-m3 via Ollama; `mistral-small-latest` as generator, LLM reranker and judge; judge concurrency 2). Three runs, all 0 errors and 0 judge failures (base re-judged under D80). Find doc hit@1 retrieved → final, Ask correctness: **base** (112) 0.78 → 0.62, 0.68 · **derivatives** (155: keywords, scenario, paraphrase, reword) 0.64 → 0.64, 0.59 · **German** (65) 0.68 → 0.64, 0.67. Findings: (1) the LLM reranker fixed 41 and broke 60 top-1s over the 306 answerable items, because it judges only the first 240 chars of each candidate, which in this corpus is the metadata header (`llm_judge._SNIPPET_LEN`), e.g. OnionDuke → MiniDuke; it helps only where retrieval missed (paraphrase: 5 fixed, 0 broke). (2) Find answered 12 of 26 unanswerable items, partly from the model's own knowledge; Ask abstained on 25 of 26. (3) Paraphrases avoiding ATT&CK vocabulary are bge-m3's weak spot (retrieved hit@1 0.77 → 0.31 vs their bases); German needs no special handling. (4) Re-judging with 4096 tokens moved every mean ≤ 0.03, a floor for meaningful run-to-run differences. Runs: `eval-runs/20261107-{130230-mitre-base,160648-mitre-derivatives,173114-mitre-de}`; scripts in `condense_test_mitre/scripts/` |
| 2026-11-08 | fcb5b58 | D81 `recap_temperature: float \| None`, blank env → `None` → no `temperature` sent. Found by the first Haiku 5.5 rerank smoke test: Anthropic's OpenAI-compatible endpoint answered 400 "`temperature` is deprecated for this model" |
| 2026-11-08 | — | **Haiku 5.5 as LLM reranker** (same three question sets, `--surfaces find --skip-judge`, recap off; `condense_test_mitre/scripts/run_haiku_rerank.sh`). Retrieval identical to the Mistral runs on all 306 answerable items (same top-12), so only the reranker model differs; same 240-char snippets. Find doc hit@1, none → Mistral Small → Haiku: **base** 0.78 → 0.62 → 0.89 · **derivatives** 0.64 → 0.64 → 0.79 · **German** 0.68 → 0.64 → 0.87. Haiku fixed 59 and broke 15 top-1s (Mistral: 41 / 60). Rerank latency mean 1.38 s, p95 2.7 s (Mistral 0.54 s / 1.0 s). This revises the first run's diagnosis: the reranking model, not the 240-char snippet, was the main cause (Haiku still misses `mitre-m07`, picking Rifdoor for Ritsol from the header). Caveat: ATT&CK is public, so part of the gain may be Haiku's own knowledge of it rather than reading the snippets; a private corpus or the cross-encoder is the fair check. Runs: `eval-runs/20261108-{095518-mitre-base,095934-mitre-derivatives,100115-mitre-de}-haiku-rerank` |

## 6. Decisions
- D73: eval is a separate in-process CLI app with its own `EvalSettings`.
- D74: RAGAS optional extra behind the `Judge` protocol; own prompts for bootstrap and abstention.
- D75: gold keyed by path + page + evidence, not chunk IDs.
- D76: citations stripped from the judged copy of each answer (found by the first real-stack run).
- D77: `answer_recall` beside `answer_correctness`; references hold only what the question asks.
- D78: gold alternatives via `group`; recall counts required groups; `complete@k`.
- D79: transient-HTTP retry with backoff in the LLM client and the RAGAS judge client.
- D80: RAGAS judge `max_tokens=4096` (default 1024 truncated long answers' claim lists).
- D81: blank `RECAP_TEMPERATURE` sends no temperature (Claude Haiku 5.5 rejects the field).

## 7. Changelog
- (on merge)
