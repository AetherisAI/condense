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
- Ranking metrics (`tests/eval/test_ranking_metrics.py`): hit@k, recall@k and MRR checked
  three ways: hand-computed tables (incl. the textbook MRR example, 11/18), a differential test
  against a naive path-based oracle on 400 seeded random rankings at chunk and doc level, and
  invariants (bounds, monotone in k, hit@k ⇔ recall@k > 0 ⇔ MRR ≥ 1/k, shift-by-one, tail
  appends). Hand mutation check: 7 planted bugs (top k−1 cutoff, hit@k = hit@1, recall over refs
  not groups, 0-based rank, last-relevant MRR, MRR cut at max k, no doc dedupe) all fail it;
  `test_metrics.py` alone missed last-relevant MRR.
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
| 2026-11-09 | 271350c | D82 `EVAL_JUDGE_PROVIDER=anthropic`: RAGAS judge via `AsyncAnthropic` + `llm_factory(provider="anthropic")` with `temperature`/`top_p` removed; base URL `/v1` stripped for the SDK; abstention completer sends no temperature; `anthropic` in `[eval]`. Found when re-judging with Haiku 5.5: its OpenAI-compatible endpoint rejects RAGAS's sampling params and JSON mode |
| 2026-11-09 | cf1da4d | `test_ranking_metrics.py`: hit@k / recall@k / MRR vs hand tables, a random-ranking oracle and invariants (§4). No metric bug found; closes the old suite's blind spot (last-relevant MRR) |
| 2026-11-09 | 0c373b8 | D83 `RERANK_TIMEOUT_S` (default 120 s) → `CrossEncoderReranker`'s httpx client, which had httpx's 5 s default. Found starting the cross-encoder MITRE run: CPU TEI (`cpu-arm64-1.9.4`, 4-vCPU Docker VM) takes ~50 s per question for 30 chunks, and the 5 s default raised `ReadTimeout`. TEI also needs `--max-batch-tokens 1024` in a 5.8 GiB Docker VM (the 16384 default OOM-kills warmup; the amd64 `cpu-latest` image is emulated on Apple Silicon and never finished warming up) |
| 2026-11-09 | fd7e73a | D84 `answer_recall` = share of reference claims the response supports (`_ReferenceRecall` around `FactualCorrectness`'s decompose + NLI); `sift-eval judge --metrics` re-scores a subset and keeps the rest. Found by the Haiku 5.5 re-judge of the MITRE runs (`condense_test_mitre/scripts/rejudge_haiku.sh`, 4,327 scoring calls, ~2.5 h at concurrency 8, base 16 failures, mostly Haiku returning a claim list as a JSON string): base answer recall Find 0.56 → 0.34, Ask 0.66 → 0.37, 31 correct answers 1 → 0. RAGAS's recall numerator counts the response's claims the reference supports, so a strict judge with D77's terse references scores 0 ÷ 0 → 0 |
| 2026-11-10 | — | **bge-reranker-v2-m3 cross-encoder as reranker**, base set only (112 items, 92 answerable; `--surfaces find --skip-judge`, recap off; `condense_test_mitre/scripts/run_crossencoder_rerank.sh`, compared by `compare_rerankers.py`). TEI `cpu-arm64-1.9.4`, `--max-batch-tokens 1024`, 4-vCPU Docker VM. Retrieval identical to the Haiku run on all 112. Find doc hit@1, none → Haiku 5.5 → cross-encoder: **0.78 → 0.89 → 0.87**; the cross-encoder fixed 15 and broke 7 (Haiku 15 / 5). Head-to-head 72 both right, 10 Haiku only, 8 cross-encoder only, 2 neither: a tie within noise (exact McNemar p ≈ 0.8). This answers the Haiku caveat for base questions: a reranker with no ATT&CK knowledge to draw on, reading full chunks, recovers most of the gain. Haiku's wins lean on inference (h02 Android 9 → foreground persistence, h03 SS7, n21 which operation came first, n23 the group behind the 2022 Ukraine attack); the cross-encoder's on exact lookups (n05 FrostyGoop's port, m07 Ritsol, which Haiku missed from the header). Only 1 cross-encoder win had its gold below the judge's 12-candidate window. The cross-encoder's top-1 score is a usable abstention signal where the cosine score isn't: top-1 median 0.98 right, 0.82 wrong, 0.74 unanswerable; abstaining below 0.5 would lose 1 of 80 right answers and withhold 5 of 12 wrong and 8 of 20 unanswerable (in-sample, so optimistic; needs a held-out check). Latency mean 46 s, p95 51 s per question (30 full chunks on CPU) vs Haiku 1.4 s: unusable off-GPU as configured. Derivatives and German sets not yet run. Run: `eval-runs/20261109-230937-mitre-base-ce-rerank` |
| 2026-11-10 | 43183be | D85 `noise_sensitivity` judges correctness against `Question: …\nAnswer: <reference>` (`_AnchoredNoiseSensitivity` around RAGAS's `NoiseSensitivity` splitting + NLI). Found checking the Haiku re-judge: RAGAS's response statements restate the question, and the bare D77 reference can't support that, so correct grounded answers scored 1.0 (base, Mistral judge: 29 Find / 30 Ask answers with faithfulness 1 and recall 1 at ≥ 0.5). Live, Haiku: `mitre-07`, `mitre-h05` 1.00 → 0.00, `mitre-h02` 0.64 → 0.00. Still rises with true extras a terse reference omits (`mitre-06` 0.67). Re-score: `condense_test_mitre/scripts/rescore_noise.sh` |
| 2026-11-10 | — | **Cross-encoder, derivatives + German sets** (same setup as the base row above; `SETS="derivatives de" run_crossencoder_rerank.sh`). Retrieval identical to the Haiku runs on all 220. Find doc hit@1, none → Haiku 5.5 → cross-encoder: **derivatives** 0.64 → 0.79 → 0.78 (151 answerable; fixed 32, broke 11 vs Haiku 29 / 7) · **German** 0.68 → 0.87 → 0.86 (63; fixed 14, broke 3 vs 15 / 3). **All three sets, 306 answerable: 0.69 → 0.84 → 0.82**; head-to-head 217 both right, 39 Haiku only, 35 cross-encoder only, 15 neither (exact McNemar p ≈ 0.73): a tie. By kind they split: **keywords** (63) Haiku 0.79, cross-encoder 0.87 (discordant 6 / 11); **scenario** (63) Haiku 0.87, cross-encoder 0.75 (12 / 4, p ≈ 0.08); paraphrase (13) 0.62 / 0.69; reword (12) 0.50 / 0.58; German 0.87 / 0.86. So the cross-encoder matches term-dense queries and Haiku the ones that need a step of inference, consistent with the base set. 4 of the cross-encoder's 35 unique wins had gold below the judge's 12-candidate window. Score as abstention signal over all sets: at t = 0.3 abstaining loses 6 of 252 right answers and withholds 15 of 54 wrong and 4 of 26 unanswerable; at 0.5, 17 / 22 / 11 (keyword derivatives produce more low-scoring right answers than base). Rerank latency mean 44–46 s, max 53 s per question on CPU (wall time was longer only because the Mac slept). Runs: `eval-runs/20261110-{092916-mitre-derivatives,154421-mitre-de}-ce-rerank` |
| 2026-11-10 | — | **Haiku 5.5 as a second RAGAS judge** on the same answers, all three sets (`condense_test_mitre/scripts/rejudge_haiku.sh` → `<run>-judge-haiku` copies; then `rescore_recall.sh` and `rescore_noise.sh` re-scored D84 recall and D85 noise sensitivity on all six runs; `compare_judges.py`). Means Mistral → Haiku, Find / Ask, **base**: faithfulness 0.92 → 0.83 / 0.91 → 0.82, correctness 0.70 → 0.65 / 0.68 → 0.64, recall 0.66 → 0.64 / 0.75 → 0.65, noise sensitivity 0.17 → 0.19 / 0.19 → 0.20, context utilization 0.86 → 0.75 / 0.75 → 0.72, relevancy 0.75 → 0.79 / 0.84 → 0.87; derivatives and German follow the same pattern. Every mean is within 0.11 except faithfulness: Haiku is 0.09–0.14 lower on all six set × surface cells, with the weakest rank agreement (Spearman 0.35–0.56). Abstention is near-identical (ρ 0.83–0.97; German Ask 0.59). The fixes are what made the judges agree: base Find recall ρ 0.25 → 0.72 (D84), noise sensitivity ρ 0.40 → 0.59 (D85). Hand check of the 4 largest base Find faithfulness gaps: Haiku right in 3 (Mistral passed claims the passages don't make, e.g. T1059.001 as an "analytic ID"); the 4th, `mitre-n10`, is a chunk-boundary split (Operation Honeybee's command; the passage starts at `temp.ini`). Item-level noise sensitivity stays noisy under both judges. Keyword variants vs their bases (Ask): correctness −0.18 / −0.21, recall −0.09 / −0.02 (Mistral / Haiku); the earlier "recall rises" reading was the D84 bug. Judge shifts can also flip small gaps (base vs derivatives Ask recall: Mistral −0.09, Haiku +0.01): compare runs under one judge, and treat gaps under ~0.1 as judge-sensitive. Haiku failures: 16 base, 11 German (of 886), 32 of 609 in the noise re-score, nearly all a claim list returned as a JSON string (`InstructorRetryException`). Runs: `eval-runs/20261107-{130230-mitre-base,160648-mitre-derivatives,173114-mitre-de}{,-judge-haiku}`; pre-fix aggregates kept as `summary.pre-d84.json` / `summary.pre-d85.json` |
| 2026-11-15 | — | D86 `EMBED_QUERY_PREFIX` / `EMBED_DOCUMENT_PREFIX`: `OpenAICompatEmbedder(prefix=)`, `factory.py` builds a query embedder (search + `search` tool) and a document embedder (ingest). Parity: `.env.example` + compose. Needed before comparing instruction-tuned embedders (Qwen3-Embedding) with bge-m3 |
| 2026-11-15 | — | **Qwen3-Embedding-0.6B vs bge-m3**, retrieval only (`--surfaces find --skip-judge`, rerank none, recap off; `condense_test_mitre/scripts/{ingest_qwen3.sh,run_embedder_compare.sh,compare_embedders.py}`). Qwen3 served by Ollama (`qwen3-embedding:0.6b`, Q8_0; bge-m3 is F16; last-token pooling and EOS confirmed in the GGUF metadata) into its own `mitre-qwen3-0.6b.db`, whose 7,278 chunks match `mitre.db`'s exactly (text + path; `CHUNK_TOKENIZER=bge-m3`). D86 query instruction from the model card, documents bare. A fresh bge-m3 run reproduced the 2026-11-07 retrieval exactly. 306 answerable, doc level, bge-m3 → Qwen3: **hit@1 0.693 → 0.676** (34 bge-only, 29 Qwen-only, exact McNemar p ≈ 0.62: a tie), hit@3 0.837 → 0.810, **hit@10 0.938 → 0.879** (31 / 9, p ≈ 0.0007), **hit@30 0.971 → 0.915** (19 / 2, p ≈ 0.0002), MRR 0.778 → 0.753. hit@1 by kind: base 0.78 → 0.73, keywords 0.71 → 0.68, scenario 0.67 → 0.63, paraphrase 0.31 → 0.46 (n = 13; 1 / 3 discordant), reword 0.50 → 0.58 (n = 12), German 0.68 → 0.70. Qwen3 loses exact-identifier lookups: `mitre-03` ("What exact technique is T0884?"), `mitre-04` (T1553) and `mitre-m07` (Ritsol) fall out of its top 30, where bge-m3 has them at rank 1–4; keyword derivatives' hit@30 0.98 → 0.87. The query instruction matters, its wording doesn't: none → hit@1 0.595 (keywords 0.37; vs bge-m3 p ≈ 0.001), a generic document-QA instruction → 0.670 (hit@30 0.912). Top-1 cosine separates right from wrong a little better (medians 0.695 / 0.619 vs 0.640 / 0.610), but unanswerable items (0.655) sit between them: still no abstention signal. Query embed latency 92 vs 116 ms mean; ingest ~14 min. Verdict: keep bge-m3; the lost top-30 coverage would cap any reranker. Runs: `eval-runs/20261115-17*-mitre-{base,derivatives,de}-{bge-m3,qwen3-0.6b,qwen3-0.6b-noinst,qwen3-0.6b-qa}-retrieval` (12) |

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
- D82: `EVAL_JUDGE_PROVIDER=anthropic` → RAGAS via the native Anthropic SDK, no sampling params.
- D83: `RERANK_TIMEOUT_S` (default 120 s) bounds the cross-encoder call; httpx's 5 s default timed out on CPU TEI.
- D84: `answer_recall` computes true recall (RAGAS's recall mode counted the response's claims); `judge --metrics`.
- D85: `noise_sensitivity` judges correctness against question + reference (RAGAS's statements restate the question).
- D86: `EMBED_QUERY_PREFIX` / `EMBED_DOCUMENT_PREFIX`, one embedder per role in `factory.py`, so instruction-tuned embedders can be compared fairly.

## 7. Changelog
- (on merge)
