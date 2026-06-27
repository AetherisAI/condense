# Engine (A1–A5) — Machine Doc

> Full design + plan + implementation record. Paired with `human.md`.

**Status:** in-progress (built, green, pending PR/merge) · **Branch:** `feat/dev-a-engine` · **Updated:** 2026-06-27

## 1. Overview
The engine half: parse → chunk → embed → upsert into libSQL, with dedup + per-tenant model-pin, plus
the ingestion agent. Implemented against the Step 0 (A0) ports, tested with `FakeEmbedder` and a real
`file:` libSQL DB. Sits behind the `VectorStore` port + the `/ingest` contract; Dev B never blocks.

## 2. Design
- **Ports implemented:** `VectorStore` (LibSQLStore), `Parser` (MarkitdownParser), `Chunker` (TokenChunker). **Consumed:** `Embedder` (via the pipeline). **New seam:** `SupportsIngest` + `IngestOutcome` in `pipelines/ingest.py`.
- **Adapters produced:** `adapters/store/libsql.py`, `adapters/parsing/markitdown.py`, `adapters/chunking/token.py`, `pipelines/ingest.py`, `agent/{client,cli}.py`, `core/hashing.py`.
- **Data flow:** ingest = `(filename, bytes)[] → ensure_ready → [dedup via content_hash] → parse → chunk → embed(batch) → upsert → IngestOutcome[]`. Agent = `walk → sha256 → GET /ingest/manifest → diff → POST /ingest`.
- **Config keys (wired by Dev B's `factory.py`):** `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `EMBED_MODEL`, `EMBED_DIM`, `CHUNK_TOKENIZER`, `CHUNK_SIZE`, `CHUNK_OVERLAP`.
- **Dependency rule:** adapters import `core` + their own lib only; `pipelines/ingest.py` imports `core` ports/types/errors/hashing only; `core/` untouched; `agent/` imports no `sift`. ✓

## 3. Plan / status (all done)
- [x] **A1 `LibSQLStore`** — DDL (model_pin/files/chunks, `F32_BLOB({dim})`), model-pin guard, idempotent upsert (`vector32(?)` + `ON CONFLICT`), `vector_distance_cos` search, `known_hashes`, `aclose`. **12 tests.**
- [x] **A2 `TokenChunker`** — bge-m3/tiktoken behind an internal protocol, 512/64 document-level windows, page mapping, global index. **6 tests.**
- [x] **A3 `MarkitdownParser`** — `convert_stream` → `Document(one Page(1))`, sha256 hash via `core.hashing`. **4 tests.**
- [x] **A4 `IngestPipeline`** + `IngestOutcome` + `SupportsIngest` — dedup, batch embed, per-file failure isolation, pin-mismatch fatal. **9 tests.**
- [x] **A5 `agent/`** — `SiftClient` (httpx) + argparse CLI; `MockTransport` tests. **8 tests.**

## 4. Test strategy
`FakeEmbedder` for ingest/chunker/agent; `LibSQLStore` against a `tmp_path` `file:` libSQL DB (score
`rel_tol=1e-4`); store behavior mirrors `FakeVectorStore`; agent uses `httpx.MockTransport`. Real-adapter
test modules are `importorskip`-guarded so base CI (`[dev]` only) stays green. **57 tests pass; ruff +
pyright clean** (libSQL is `Any`-typed at the seam — stub-less C extension).

## 5. Implementation log
| Date | Commit | Change |
|------|--------|--------|
| 2026-06-27 | b650ceb | A1–A5 engine + `core/hashing` + docs (built via 5 parallel subagents); pyright fix (libsql `Any`) |
| 2026-06-27 | (merge) | merge `origin/main` — Quentin docs + team `CLAUDE.md` |

## 6. Decisions
A1 src-layout · A2 async ports · A3 async-over-sync store · A4 score=1−distance · A5 explicit tenant ·
A6 shared hash · A7 markitdown one-page · A8 chunk-512 · A9 ingest seam — see [`../DECISIONS.md`](../DECISIONS.md).

## 7. Changelog
- v0-pending — engine A1–A5 implemented and green; awaiting PR + A6 integration.
