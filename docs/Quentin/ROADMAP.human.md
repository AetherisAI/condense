# Dev B Roadmap — Human Digest

> The 2-minute version. Full detail + per-task plans: [`ROADMAP.md`](./ROADMAP.md). Paired companion (enforced).

**Updated:** 2026-06-27 · **Owner:** Quentin (Dev B)

## What we're building
The **surface** of Condense: take a query → embed it → pull a wide candidate set from the vector store → **rerank to the single best** → recap it → serve over an authed FastAPI + a small React UI, all in Docker. Arthur builds the engine (ingest + storage); we meet at the `VectorStore` port and never block on each other.

## The plan in one breath
Ten work packages, each its own `feat/<slice>` branch, built **against fakes** so nothing waits on Arthur:

**WP0 Contracts & fakes** → **WP1 Config & factory** → **WP2 Embedder** ∥ **WP3 Completer** → **WP4 LLM-judge rerank** → **WP5 Search pipeline** → **WP6 API (auth+tenant)** → **WP7 React UI** → **WP8 Docker compose** → *WP9 TEI cross-encoder (optional)*.

## Milestones (what "done" looks like at each step)
- **M1:** single best result end-to-end, fakes only, no external services.
- **M2:** real search against Ollama/Mistral with LLM-judge + recap.
- **M3:** `/search` + `/healthz` over HTTP with bearer auth.
- **M4:** search + ingest panels in the browser.
- **M5:** `docker compose up` → swap fake store for Arthur's libSQL → joint smoke test.

## Decisions already taken (see DECISIONS.md)
- **Turso/libSQL native vectors** — no external vector DB (D2).
- **Rerank = LLM-judge by default**, cross-encoder optional behind the port (D4).
- **Recap ON**, folded into the judge's single call (D5).
- **Config-driven factory** wires fakes by default (D6).
- Everything behind ports → swappable by config, testable in isolation.

## What I need from you / Arthur
1. **Confirm the `core/` contracts** — I've *proposed* the port signatures, `Hit`/`Chunk` types, and `api/schemas.py`. They're co-owned; Arthur should sanity-check before we build on them (the one real coupling).
2. **`/ingest` response + manifest shape** — align with Arthur's ingest pipeline.
3. Nothing else blocks — WP0 is implementable now.

## Risks worth knowing
- **Contract drift with Arthur** → I fetch origin every WP and treat `core/` changes as joint PRs.
- **LLM-judge token cost** at 30 candidates → cap the judge to ~10–12; cross-encoder is the escape hatch.
- Inference endpoint quirks (Ollama `/v1/embeddings`, TEI bare-array `/rerank`) → handled in the adapter plans.

## Status / next action
Roadmap + WP0 plan written. **Next:** implement WP0 (contracts & fakes) — ready to launch subagents on `docs/active/machine.md` once you're back and have green-lit the `core/` contracts with Arthur.
