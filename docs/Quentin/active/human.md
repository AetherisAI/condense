> **Desktop WP COMPLETE on `feat/desktop-standalone`** (D60–D67), merge pending → v0.4.0. This file now tracks the parallel **eval-harness** WP.

# Eval harness (`sift-eval`) — Human Doc

> **≤500 words. Decision-first.** The fast read; full detail in `machine.md`.

**Status:** in-progress &nbsp;·&nbsp; **Branch:** `feat/eval-harness` &nbsp;·&nbsp; **Updated:** 2026-11-15

## What & why
Tuning changes (chunking, rerank, RETRIEVE_K, LLM) were judged by eye. `sift-eval` scores
Find (`/search`) and Ask (`/v1/answer`) against a golden set: retrieval (recall/precision@k,
hit@k, MRR), LLM-judged answer quality, noise robustness, abstention, per-stage latency. Each
run writes a JSON + HTML report; `compare` diffs two runs.

## Key decisions
- **D73:** a **CLI, not an app feature**. It runs the real pipeline in-process
  (`factory.build_container`): `/search` returns only FINAL_K=1, and recall@k, stage timings
  and noise injection need internals. Own `EvalSettings` (`EVAL_*`); product code
  never imports `sift.eval`.
- **D74:** LLM-judged metrics use **RAGAS 0.4 (collections API)** as an optional `[eval]` extra
  behind a small `Judge` protocol (`FakeJudge` in tests). `langchain-community<0.4` is pinned
  (RAGAS 0.4.3 breaks on 0.4.x).
- **D75:** gold relevance is keyed by **path (+ optional page, + optional evidence quote)**, not
  chunk IDs, so a golden set survives re-chunking.
- **D76:** the judge scores answers with **inline citations stripped**, because RAGAS counted
  `(file.md, p.1)` as an unsupported claim. Stored answers stay verbatim.
- **D77:** **answer recall** joins answer correctness, an F1 that also charges for true details
  the reference omits. References now hold only what the question asks. **D84–D85:** we fix
  RAGAS's recall and noise-sensitivity scoring, which marked correct answers to terse
  references wrong.
- **D78:** gold entries sharing a `group` are alternatives; recall counts required groups;
  `complete@k` asks if all were found.
- **D79–D82:** LLM client and judge **retry transient errors**; judge gets 4096 output tokens.
  Claude: blank `RECAP_TEMPERATURE` sends no sampling params; Claude judges use its SDK.

## Ports / interfaces touched
- No `core/` changes.
- **D86:** `EMBED_QUERY_PREFIX` / `EMBED_DOCUMENT_PREFIX`; `factory.py` builds one embedder
  per role, so instruction-tuned embedders (Qwen3) compare fairly with bge-m3.
- `SearchPipeline` gains an additive `trace()` (raw retrieval, reranked list, recap context,
  stage timings) and a public `recap()`. `search()` is a thin wrapper, behavior unchanged.
- `factory.build_container(..., ephemeral_conversations=False)`: Ask eval runs don't touch real
  chat history. `factory.build_completer()` is now public, for the judge LLM.

## Risks / open questions
- Weak judges fail RAGAS's structured output (counted `None`, reported). Use a strong judge,
  not the generator.
- Latency is in-process (no HTTP/auth), including rate-limit backoff.
- Bootstrapped questions copy chunk wording, which flatters retrieval.
- `factory.py` changes are flagged to Arthur.

## Status / next action
- MITRE eval done (332 items; `machine.md` §5). Top-1 over 306 answerable: none 0.69,
  Haiku 5.5 0.84, the bge-reranker-v2-m3 cross-encoder 0.82 (a tie; no LLM, but ~46 s/query
  on CPU). Find answered 12 of 26 unanswerable items.
- A Haiku 5.5 re-judge matches Mistral's means within 0.11 after D84–D85, except faithfulness
  (Haiku 0.09–0.14 stricter; right in 3 of 4 hand checks).
- Retrieval metrics are oracle-tested (`machine.md` §4).

## Pointer
- Plan + code: [`./machine.md`](./machine.md) · user guide: [`docs/evaluation.md`](../../evaluation.md)
