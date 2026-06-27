# Dev A Roadmap — Human Digest

> The 2-minute version. Full detail + per-WP plans: [`ROADMAP.md`](./ROADMAP.md). Paired companion (enforced).

**Updated:** 2026-06-27 · **Owner:** Arthur (Dev A)

## What we're building
The **engine** of Condense: files → parse → chunk → embed → store in Turso/libSQL, with dedup and a
per-tenant model-pin, plus the ingestion **agent** that feeds the host over the LAN. Dev B builds the
surface (search/rank/recap/serve/UI); we meet at the `VectorStore` port and the `/ingest` contract and
never block each other.

## The plan in one breath
Seven slices, built against fakes: **A0 contracts & fakes** → **A1 libSQL store** → **A2 chunker** ∥
**A3 parser** → **A4 ingest pipeline** → **A5 agent CLI** → *A6 integration (joint)*. **A0–A5 are done
and green; A6 is the joint factory-swap + smoke.**

## Done (what "done" means here)
- **A0** = the shared Step 0 (and Dev B's planned WP0): real `core/` contracts + fakes, not a proposal.
- **A1** `LibSQLStore` passes the same behavior contract as `FakeVectorStore` against a real `file:` DB.
- **A2 / A3** chunker (512 windows, bge-m3 tokenizer) + parser (markitdown → one page).
- **A4** ingest pipeline (dedup, per-file isolation) + the `SupportsIngest` seam for Dev B's route.
- **A5** agent CLI (walk → hash → manifest diff → upload).
- 57 tests, ruff + pyright clean.

## Decisions already taken (see DECISIONS.md)
- **All ports async**, **src/sift layout**, **score = 1 − cosine-distance**, **explicit `tenant`**,
  **chunk 512 (reranker-bound, not 8192)**, **markitdown one-page**, shared **sha256** hash.

## What I need from / owe Quentin
1. **Contracts are now real code** — build WP1+ against the actual ports.
2. **Reconcile two deltas:** ports are **async**; package is **src/sift/** (your D11 assumed flat `sift/`).
   Both are mechanical for fakes-based code.
3. **`/ingest` wire shape** — multipart `files` + `?tenant=` + `{hashes:[]}`; you own the routes +
   the `IngestOutcome → IngestFileResult` mapping.

## Risks worth knowing
- **README drift:** your docs predate **v6** (reranker default = cross-encoder; shared bge-m3 embedder).
- **libSQL untyped C ext** → `Any` at the seam, behavior pinned by tests.
- **Chunk size** bounded by your embedder `num_ctx` + reranker ~1024 window → startup validation.

## Status / next action
Engine green on `feat/dev-a-engine`. **Next:** push + PR; then A6 integration (factory swap + joint
smoke over the LAN).
