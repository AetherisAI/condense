# Dev A Roadmap — The Engine (ingest + storage)

**Updated:** 2026-06-27 · **Owner:** Arthur (Dev A) · Companion: [`ROADMAP.human.md`](./ROADMAP.human.md)

## What we're building
The **engine** half of Condense: raw files → parse → chunk → embed → upsert into the Turso/libSQL
vector store, with content-hash dedup and a per-tenant model-pin. Plus the ingestion **agent CLI**
that walks a folder, diffs against the manifest, and uploads new files over the LAN. We meet Dev B
(the surface) at the `VectorStore` port and the `/ingest` contract; ports + fakes keep either side
from blocking the other.

## Work packages
| WP | Slice | Deliverable | Status |
|----|-------|-------------|--------|
| **A0** | contracts & fakes | `core/` types + 6 async ports + errors; `FakeEmbedder`/`FakeVectorStore`/`NullReranker`; `api/schemas.py`; CI scaffolding. **(= shared Step 0 / Dev B's planned WP0 — now real code, not a proposal.)** | ✅ done |
| **A1** | libsql store | `LibSQLStore` — schema, per-tenant model-pin, idempotent upsert, brute-force `vector_distance_cos` search, `known_hashes`, tenant filtering. | ✅ done |
| **A2** | chunking | `TokenChunker` — config-driven tokenizer (bge-m3 default / tiktoken), 512/64 document-level windows. | ✅ done |
| **A3** | parsing | `MarkitdownParser` — bytes → `Document` (one `Page(1)`), sha256 content hash. | ✅ done |
| **A4** | ingest pipeline | `IngestPipeline` — parse→chunk→embed→upsert, dedup, per-file isolation; `IngestOutcome` + `SupportsIngest` seam. | ✅ done |
| **A5** | agent | `agent/` CLI — walk → hash → GET manifest → upload new, bearer auth. | ✅ done |
| **A6** | integration | Wire real adapters in `factory.py` (with Dev B); joint smoke over the LAN. | ⏳ pending (joint) |

## Milestones
- **M-A1:** ingest pipeline green end-to-end with fakes (no Turso). ✅
- **M-A2:** `LibSQLStore` passes the same behavior contract as `FakeVectorStore` against a real `file:` libSQL DB. ✅
- **M-A3:** agent CLI ingests a folder against a live `/ingest` (needs Dev B's routes). ⏳
- **M5 (joint):** `factory.py` swaps `FakeVectorStore → LibSQLStore`; full smoke over the LAN. ⏳

## Decisions already taken (see DECISIONS.md)
- **src/sift/ src-layout** (A1) — reconcile with Quentin's flat-`sift/` assumption (his D11).
- **All six ports are `async def`** (A2) — engine I/O + FastAPI; sync libsql wrapped in a worker thread.
- **`Hit.score = 1 − vector_distance_cos`** (A4) — cosine distance → similarity, matches `FakeVectorStore`.
- **`upsert`/`ensure_ready` take an explicit `tenant`** (A5); model-pin is per-tenant.
- **Chunk size 512, reranker-bound** (A8) — bge-reranker-v2-m3 quality-caps ~1024 combined; 8192 rejected.

## What I need from / owe Dev B
1. **The `core/` contracts are now real code** (A0) — build WP1+ against the actual ports, not a proposal.
2. **`/ingest` + `/ingest/manifest` wire shape** — the agent hard-codes multipart `files` + `?tenant=` + `{hashes:[]}`; Dev B's routes own these, plus the `IngestOutcome → IngestFileResult` mapping.
3. **Reconcile two contract deltas:** ports are **async** (unspecified in his WP0 plan); package is **src/sift/** (not flat `sift/`). Both are mechanical for fakes-based code.

## Risks
- **Contract drift with Dev B** — his docs predate README v6 (cross-encoder default, shared bge-m3) and assume flat `sift/`; reconcile on his next fetch.
- **libSQL is a stub-less C extension** → `Any`-typed at the seam; behavior covered by 12 store tests.
- **Chunk-size config** is bounded by Dev B's embedder `num_ctx` + reranker window — validate at startup.

## Status / next action
Engine implemented and green (57 tests, ruff + pyright clean) on `feat/dev-a-engine`. **Next:** push +
PR; then A6 integration with Dev B (factory swap + joint smoke).
