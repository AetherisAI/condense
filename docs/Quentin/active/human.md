> **Desktop WP COMPLETE on `feat/desktop-standalone`** (D60–D67), merge pending → v0.4.0 (its docs archive at that merge). This file now tracks the parallel **eval-harness** WP.

# Eval harness (`sift-eval`) — Human Doc

> **≤500 words. Decision-first.** This is the fast-read companion to `machine.md`. If you only have two minutes, read this.

**Status:** in-progress &nbsp;·&nbsp; **Branch:** `feat/eval-harness` &nbsp;·&nbsp; **Updated:** 2026-11-05

## What & why
Condense had no way to measure quality, so every tuning change (chunk size, rerank strategy,
RETRIEVE_K, LLM) was judged by eye. `sift-eval` scores both Find (`/search`) and Ask
(`/v1/answer`) against a golden question set. Metrics: recall/precision@k (plus hit@k and MRR),
answer relevancy, faithfulness, answer correctness, context utilization, noise robustness,
abstention on unanswerable questions, and per-stage latency. Each run writes a JSON + HTML report,
and `compare` diffs two runs.

## Key decisions
- **D73:** a **CLI, not an app feature**. It runs the real pipeline in-process through
  `factory.build_container`, because `/search` returns only FINAL_K=1, and recall@k, per-stage
  timings and noise injection all need internals HTTP doesn't expose. It is its own little app
  (like `agent/`) with its own `EvalSettings` (`EVAL_*`). Product code never imports `sift.eval`.
- **D74:** LLM-judged metrics use **RAGAS 0.4 (collections API)** as an optional `[eval]` extra
  behind a small `Judge` protocol (`FakeJudge` in tests). `langchain-community<0.4` is pinned
  because RAGAS 0.4.3 won't import against 0.4.x. Bootstrap and the abstention check use our own
  small prompts through the existing `Completer`.
- **D75:** gold relevance is keyed by **path (+ optional page, + optional evidence quote)**, not
  chunk IDs, so a golden set survives re-chunking.

## Ports / interfaces touched
- No `core/` changes.
- `SearchPipeline` gains an additive `trace()`, which returns the raw retrieval list, the
  reranked list, the recap context and per-stage timings, plus a public `recap()`. `search()` is a
  thin wrapper with identical behavior.
- `factory.build_container(..., ephemeral_conversations=False)`: Ask eval runs don't touch real
  chat history. `factory.build_completer()` is now public, for the judge LLM.

## Risks / open questions
- Small local judge models often fail RAGAS's structured output. Failures count as `None` and are
  reported per metric. Use a strong judge, ideally not the generator model (the report warns if
  they're the same).
- Measured latency is in-process and leaves out HTTP, auth and serialization.
- Bootstrapped questions copy the wording of their source chunk, so retrieval looks better than it
  is. Rewrite them before trusting the numbers.
- `factory.py` is a shared seam, so the change is flagged to Arthur in the channel.

## Status / next action
- Plan approved. Implementing task by task (see `machine.md` §3).

## Pointer
- Full plan, tasks, and code: [`./machine.md`](./machine.md) · user guide: [`docs/evaluation.md`](../../evaluation.md)
