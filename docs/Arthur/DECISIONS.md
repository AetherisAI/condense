# Decision Log — Condense (Dev A / Engine)

> Global, append-only. **Never archived.** At every important fork I record the best guess from the
> architecture + plan and move on, for traceability. Format: **Decision · Why · Alternatives · Basis.**
> Paired with Dev B's [`../Quentin/DECISIONS.md`](../Quentin/DECISIONS.md). `[A<n>]` = Arthur's engine
> decisions. Newest at the bottom.

---

## 2026-06-27 — A1: Package uses a `src/sift/` src-layout  [global · reconcile w/ Quentin D11]
- **Decision:** The package lives under `src/sift/` (src-layout), not a flat `sift/` at the repo root.
- **Why:** Can't accidentally import the working copy; tests run against the installed package; clean test/CI boundary. Wired via `pyproject` `packages = ["src/sift"]`.
- **Alternatives:** Flat `sift/` (Quentin's D11 assumption from the README module map) — works but weaker import isolation.
- **Basis:** User chose src-layout at Step 0. Quentin's fakes-based code is unaffected beyond the import path; reconcile on his fetch.

## 2026-06-27 — A2: All six ports are `async def`  [global]
- **Decision:** `Embedder`, `Reranker`, `Completer`, `VectorStore`, `Parser`, `Chunker` are all `async`.
- **Why:** The real adapters are I/O-bound (Ollama/TEI/LLM HTTP, libSQL) behind async FastAPI; one uniform rule. Pure-CPU adapters just never await.
- **Alternatives:** Sync ports + threadpool offload — caps concurrency, awkward fan-out. Mixed sync/async — bikeshedding about which is which.
- **Basis:** User chose all-async at Step 0; flipping sync↔async after freeze touches every adapter, so locked early.

## 2026-06-27 — A3: `LibSQLStore` is async-over-sync via a single-worker executor  [WP: libsql]
- **Decision:** The `libsql` SDK is synchronous, so the store owns ONE connection on a `ThreadPoolExecutor(max_workers=1)`, created lazily on that thread; every async method dispatches one executor job (incl. `commit()`); an `asyncio.Lock` guards writes.
- **Why:** A sqlite/libsql connection isn't safe across threads; a single worker keeps it thread-bound and serializes ops (single-writer), satisfying the async port without blocking the event loop.
- **Alternatives:** `asyncio.to_thread` with a multi-thread pool (cross-thread connection misuse); connection-per-call (reopens the file, loses any replica session); the beta async `pyturso` engine (the rewrite we avoid).
- **Basis:** libsql 0.1.11 is sqlite3-style + sync; verified vector SQL on a local file DB.

## 2026-06-27 — A4: `Hit.score = 1 − vector_distance_cos`  [WP: libsql]
- **Decision:** libSQL returns cosine *distance*; the store converts to similarity so `Hit.score` is ≈1.0 for an exact match, matching `FakeVectorStore`.
- **Why:** One score convention across the real and fake stores (and what the reranker/API expect).
- **Alternatives:** Surface raw distance — rejected: inverts ordering and breaks fake/real parity.
- **Basis:** Turso docs (distance = 1 − similarity); verified (identical vectors → distance 0.0).

## 2026-06-27 — A5: `upsert`/`ensure_ready` take an explicit `tenant`; model-pin is per-tenant  [global]
- **Decision:** `upsert(chunks, tenant)` and `ensure_ready(model, dim, tenant)` carry `tenant`; the pin lives in a per-tenant `model_pin` row.
- **Why:** Resolves the README §2-vs-§10 conflict toward §10 ("VectorStore methods already take tenant"); tenant is store-routing, not chunk content. Sets up database-per-tenant later via the factory.
- **Alternatives:** `tenant` as a `Chunk` field — pollutes the parser/chunker with a routing concern.
- **Basis:** README §10 + §6 (per-tenant model-pin).

## 2026-06-27 — A6: One shared `content_hash` (`core/hashing.py`, sha256 of raw bytes)  [global]
- **Decision:** A single stdlib `content_hash(data) -> str` used by the parser (Document hash), the pipeline (pre-parse dedup), and the agent (manifest diff).
- **Why:** Structurally guarantees "the hashes agree" — the manifest the agent diffs against and the store's `known_hashes` are computed identically.
- **Alternatives:** Each layer hashes independently — risks silent drift between the agent's diff and the store.
- **Basis:** README §6 (content-hash dedup); Dev A plan.

## 2026-06-27 — A7: `MarkitdownParser` emits one `Page(number=1)` per file  [WP: parsing]
- **Decision:** markitdown returns a single markdown string (no page boundaries locally), so every file becomes one `Page(1)`. The `page` field stays in the contract.
- **Why:** Real per-page extraction needs a per-PDF path (pypdf); deferred. Keeping the page-level citation field means adding real pages later is an adapter swap, not a schema change.
- **Alternatives:** Hybrid pypdf-per-page now — more deps + loses markitdown's PDF tables; user chose markitdown-only.
- **Basis:** Verified markitdown 0.1.6 drops page numbers locally (only Azure adds them); user decision.

## 2026-06-27 — A8: Chunk size 512, tokenizer config-driven (bge-m3 default); 8192 rejected  [WP: chunking]
- **Decision:** `CHUNK_SIZE=512`, `CHUNK_OVERLAP=64`; `CHUNK_TOKENIZER` selects bge-m3 (default, exact reranker-aligned tokens) or tiktoken (offline fallback). Document-level windows.
- **Why:** bge-reranker-v2-m3 was fine-tuned at 512 passage / 1024 combined and degrades above ~1024 — 512 sits at its trained length. bge-m3's own tokenizer makes "512" honest in the reranker's tokenization.
- **Alternatives:** 8192-token chunks (bge-m3's max) — embed fine but the reranker silently degrades out-of-distribution (verified, 2/2 adversarial). tiktoken default — approximate vs the multilingual reranker.
- **Basis:** Verified bge-m3 (8192, but Ollama truncates without num_ctx), bge-reranker-v2-m3 (rec. ≤1024), libSQL (no token limit). User: "use the reranker as recommended."

## 2026-06-27 — A9: Ingest seam = `IngestOutcome` + `SupportsIngest` in `pipelines/ingest.py`  [WP: ingest]
- **Decision:** The pipeline returns a local `IngestOutcome` dataclass and exposes a `SupportsIngest` Protocol; there is **no** formal `IngestPort` in `core/`.
- **Why:** Dependency rule — `api/ → pipelines`, so the route depends on the pipeline directly; `IngestOutcome` must not import `api/schemas`. Dev B stubs `SupportsIngest` until the real pipeline lands; the route maps `IngestOutcome → IngestFileResult`.
- **Alternatives:** Put it in `core/ports` — over-couples core to a non-adapter composition. Return `api/schemas` types — violates the dependency rule.
- **Basis:** README §2 dependency rule; Dev A plan §4; reconciled with Quentin (`docs/dev-split.md` §3).
