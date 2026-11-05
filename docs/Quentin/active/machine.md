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
  - recall@k = gold entries found in top-k ÷ gold entries.
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
    (lower is better).
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
**Files:** `src/sift/eval/{__init__,golden,matching,metrics}.py`, `tests/eval/test_{golden,matching,metrics}.py`

### Task 4: config + collect (Find + Ask)
**Files:** `src/sift/eval/{config,collect}.py`, `tests/eval/test_collect.py`

### Task 5: judge protocol + RAGAS adapter
**Files:** `src/sift/eval/{judge,ragas_judge}.py`, `tests/eval/test_judge.py`

### Task 6: noise sweep
**Files:** `src/sift/eval/noise.py`, `tests/eval/test_noise.py`

### Task 7: report + CLI (run / judge / compare) + packaging
**Files:** `src/sift/eval/{report,runner,cli}.py`, `pyproject.toml`, `.gitignore`, `tests/eval/test_cli.py`

### Task 8: validate + bootstrap
**Files:** `src/sift/eval/{validate,bootstrap}.py`, `tests/eval/test_{validate,bootstrap}.py`

### Task 9: docs + guards
**Files:** `docs/evaluation.md`, `evals/golden.example.jsonl`, `.env.example`, `CLAUDE.md` §9, `docs/channel/from-quentin.md`, `tests/contract/test_layering.py`

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
| 2026-11-05 | — | WP opened; plan approved |

## 6. Decisions
- D73: eval is a separate in-process CLI app with its own `EvalSettings`.
- D74: RAGAS optional extra behind the `Judge` protocol; own prompts for bootstrap and abstention.
- D75: gold keyed by path + page + evidence, not chunk IDs.

## 7. Changelog
- (on merge)
