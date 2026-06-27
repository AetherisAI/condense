# Engine (A1–A5) — Human Doc

> ≤500 words. Fast-read companion to [`machine.md`](./machine.md).

**Status:** built, green, pending PR/merge · **Branch:** `feat/dev-a-engine` · **Updated:** 2026-06-27

## What & why
The engine half of Condense is implemented: parse → chunk → embed → upsert into Turso/libSQL, with
content-hash dedup and a per-tenant model-pin, plus the ingestion agent that feeds the host over the
LAN. All built against the Step 0 ports and tested with fakes + a real `file:` libSQL DB, so it never
blocked on Dev B.

## What's in it
- **`LibSQLStore`** — the real `VectorStore`: `F32_BLOB(1024)` + `vector_distance_cos`, idempotent
  upsert, per-tenant pin, `known_hashes`. Async-over-sync (one connection on a single worker thread).
- **`TokenChunker`** — 512/64 document-level windows; bge-m3 tokenizer (default) or tiktoken.
- **`MarkitdownParser`** — bytes → `Document` (one `Page(1)`), sha256 hash.
- **`IngestPipeline`** — dedup + batch embed + per-file failure isolation; exposes `SupportsIngest`
  + `IngestOutcome` (the seam Dev B's `/ingest` route stubs until this lands).
- **`agent/`** — walk → hash → manifest diff → upload.

## Key decisions
- **All ports async**, **src/sift layout** — `DECISIONS.md` A1/A2.
- **`score = 1 − cosine-distance`** (fake/real parity) — A4.
- **Chunk 512, reranker-bound** (not 8192; bge-m3 tokenizer) — A8.
- **One shared sha256 `content_hash`** — A6.

## Ports / interfaces touched
Implements `VectorStore`, `Parser`, `Chunker`; consumes `Embedder`; adds the `SupportsIngest` seam.

## Risks / open questions
- **Reconcile with Quentin:** ports are **async** and the package is **src/sift/** (his D11 assumed flat
  `sift/`) — mechanical for his fakes-based code, but flag on his next fetch.
- His docs predate **README v6** (cross-encoder rerank default; shared bge-m3).
- libSQL is an untyped C extension → `Any` at the seam (behavior pinned by 12 tests).

## Status / next action
Green (57 tests, ruff + pyright clean) on `feat/dev-a-engine`. **Next:** push + open PR; then **A6** —
swap `FakeVectorStore → LibSQLStore` in `factory.py` with Dev B and run the joint LAN smoke.

## Pointer
Full design + per-component status: [`./machine.md`](./machine.md).
