# WP0 — Contracts & Fakes — Human Doc

> ≤500 words. Fast-read companion to [`machine.md`](./machine.md).

**Status:** planned — ready to implement · **Branch:** `feat/contracts` · **Updated:** 2026-06-27

## What & why
The first work package and the unblocker for everything else. It freezes the **interfaces** Dev B codes against (`core/` types + ports, `api/schemas.py`) and ships three **fakes** (`FakeEmbedder`, `FakeVectorStore`, `NullReranker`). Once these exist, every later slice can be built and tested with **zero external services** (no Turso, Ollama, or TEI) and with **no dependency on Arthur**.

## Key decisions
- **`core/` is stdlib-only** (dataclasses, not pydantic) to honour the dependency rule; pydantic lives at the API boundary (`api/schemas.py`). — `DECISIONS.md` D6
- **Ports are `typing.Protocol`** (structural) — adapters don't inherit anything, they just match the shape.
- **Fakes are deterministic** (sha256-seeded unit vectors; in-memory cosine) so tests are stable and offline. Mirrors Turso's cosine semantics. — D2
- **Package is `sift/`** per the README module map — a placeholder codename. Renaming later is a mechanical import sweep. — **D11 (confirm with Arthur)**

## Ports / interfaces touched
Proposes all six ports — `Embedder`, `Reranker`, `Completer`, `VectorStore`, `Parser`, `Chunker` — plus `Hit`/`Chunk`/`Document` types and the response schemas. **`core/` is co-owned**, so these are a *proposal* for Arthur to sign off.

## Risks / open questions
- **The one real coupling:** `core/` contracts + `api/schemas.py` must match what Arthur's engine produces. Mitigation: this is a small, reviewable PR; I fetch origin before building on it. **Needs Arthur's nod before WP1+.**
- `Hit`/`Chunk` field names are my best guess from README §6/§71 — easy to adjust, but adjust *before* adapters depend on them.

## Status / next action
Plan is complete with full code and TDD steps (7 tasks, ~30 commits). **Next:** on your go-ahead, launch subagent-driven implementation of `machine.md` task-by-task on `feat/contracts`. Recommend a quick contract review with Arthur first, since `core/` is shared.

## Pointer
Full design, file list, and per-task code: [`./machine.md`](./machine.md).
