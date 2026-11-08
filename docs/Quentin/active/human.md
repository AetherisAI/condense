> **Desktop WP COMPLETE on `feat/desktop-standalone`** (D60–D67), merge pending → v0.4.0. This file now tracks the parallel **eval-harness** WP.

# Eval harness (`sift-eval`) — Human Doc

> **≤500 words. Decision-first.** The fast read; full detail in `machine.md`.

**Status:** in-progress &nbsp;·&nbsp; **Branch:** `feat/eval-harness` &nbsp;·&nbsp; **Updated:** 2026-11-08

## What & why
Condense had no way to measure quality: every tuning change (chunk size, rerank, RETRIEVE_K, LLM)
was judged by eye. `sift-eval` scores Find (`/search`) and Ask (`/v1/answer`) against a golden
set: recall/precision@k, hit@k, MRR, answer relevancy, faithfulness, answer correctness and
recall, context utilization, noise robustness, abstention, per-stage latency. Each run writes a
JSON + HTML report; `compare` diffs two runs.

## Key decisions
- **D73:** a **CLI, not an app feature**. It runs the real pipeline in-process through
  `factory.build_container`, because `/search` returns only FINAL_K=1, and recall@k, stage
  timings and noise injection need internals. Own `EvalSettings` (`EVAL_*`); product code
  never imports `sift.eval`.
- **D74:** LLM-judged metrics use **RAGAS 0.4 (collections API)** as an optional `[eval]` extra
  behind a small `Judge` protocol (`FakeJudge` in tests). `langchain-community<0.4` is pinned
  because RAGAS 0.4.3 won't import against 0.4.x.
- **D75:** gold relevance is keyed by **path (+ optional page, + optional evidence quote)**, not
  chunk IDs, so a golden set survives re-chunking.
- **D76:** the judge scores answers with **inline citations stripped**, because RAGAS counted
  `(file.md, p.1)` as an unsupported claim (live: 0.5 → 1.0 on a correct answer). Stored answers
  stay verbatim.
- **D77:** **answer recall** joins answer correctness, an F1 that also charges for true details
  the reference omits. References now hold only what the question asks.
- **D78:** gold entries sharing a `group` are alternatives; recall counts required groups;
  `complete@k` asks if all were found. `compare` warns when the set changed.
- **D79/D80:** LLM client **retries 429/502/503/504** (~1 min backoff); judge retries 10×,
  4096 output tokens. Found by the first MITRE run. **D81:** blank `RECAP_TEMPERATURE` sends
  none (Haiku 5.5 rejects it).

## Ports / interfaces touched
- No `core/` changes.
- `SearchPipeline` gains an additive `trace()`, which returns the raw retrieval list, the
  reranked list, the recap context and per-stage timings, plus a public `recap()`. `search()` is a
  thin wrapper with identical behavior.
- `factory.build_container(..., ephemeral_conversations=False)`: Ask eval runs don't touch real
  chat history. `factory.build_completer()` is now public, for the judge LLM.

## Risks / open questions
- Small local judges often fail RAGAS's structured output; failures count as `None`, reported
  per metric. Use a strong judge, ideally not the generator (the report warns).
- Latency is in-process (no HTTP/auth) and includes any rate-limit backoff.
- Bootstrapped questions copy chunk wording (flatters retrieval). Rewrite them.
- `factory.py` is a shared seam, so the change is flagged to Arthur in the channel.

## Status / next action
- First MITRE eval done (332 items, 0 errors; `machine.md` §5). The LLM reranker broke 60
  top-1s and fixed 41: it sees only each candidate's 240-char header. Find answered 12 of 26
  unanswerable items. Next: Haiku 5.5 as reranker.

## Pointer
- Full plan, tasks, and code: [`./machine.md`](./machine.md) · user guide: [`docs/evaluation.md`](../../evaluation.md)
