> **Historical (Step-0, 2026-06-27)** — for current state see `README.md`, `docs/api-schema.md`, `CLAUDE.md` §9.

# Two-developer split & coordination

How Sift is built by two people in parallel against the frozen Step 0 contracts.
**Dev A** = Arthur (engine: ingest + storage). **Dev B** = co-dev (surface: retrieve + rank + serve).

## Ownership

**Dev A — engine (ingest + storage)**
- `adapters/store/libsql.py` (LibSQLStore), `adapters/parsing/markitdown.py`,
  `adapters/chunking/token.py`, `pipelines/ingest.py`, `agent/`, plus the shared
  `core/hashing.py`. Tests use `FakeEmbedder`.

**Dev B — surface (retrieve + rank + serve)**
- `adapters/embedding/openai_compat.py`, `adapters/rerank/*`, `adapters/llm/*`,
  `pipelines/search.py`, `api/` (routes + deps), `config.py`, `factory.py`, `web/`.
  Tests use `FakeVectorStore`.

## The contract between them

**1. VectorStore port — Dev B consumes, never imports the impl.**
Dev B codes against the `VectorStore` Protocol (`core/ports.py`) and gets the instance from
`factory.py`; it never imports `adapters/store/libsql.py`. By method:
- Dev B uses `search`, `ensure_ready` (model-pin check on search), `known_hashes` (manifest route).
- Dev A owns `upsert` (ingest). Tests use `adapters/store/fake.py`.

**2. Shared seam — treat as joint.**
`core/` (types + ports + hashing + errors), `api/schemas.py`, and `factory.py` wiring are shared.
Contract changes to `core/` or the API schema get a dedicated small PR both review. Fetch `origin`
at the start of every work package and reconcile drift immediately.

**3. `/ingest` route → pipeline seam.**
There is no formal "IngestPort" — by the dependency rule `api/ → pipelines`, so Dev B's `/ingest`
route depends on the pipeline directly. Two facts:
- The HTTP contract Dev B's UI + auth need is already frozen in `api/schemas.py`
  (`IngestResponse` / `IngestFileResult` / `IngestStatus`) — Dev B is **not blocked**.
- The internal seam is `SupportsIngest` (a Protocol in `pipelines/ingest.py`):
  `async def ingest(files: Sequence[tuple[str, bytes]], tenant) -> list[IngestOutcome]`.
  Until Dev A's real `IngestPipeline` lands, Dev B wires a **stub** satisfying `SupportsIngest`
  behind the route, so the route + auth + UI can be built and tested. The route maps
  `IngestOutcome → IngestFileResult`; `ModelPinMismatch → HTTP 409`.

**4. Integration point.**
In `factory.py`, swap `FakeVectorStore → LibSQLStore` and `FakeEmbedder →` the real
`OpenAICompatEmbedder`, then run the joint smoke on the host (M5): agent ingests a sample folder
over the LAN → search via the UI → confirm single best result + path + recap → re-run the agent to
confirm dedup skips everything. Gotcha at the swap: the model-pin must agree on both sides
(`EMBED_MODEL=bge-m3`, `EMBED_DIM=1024`) or `LibSQLStore` raises `ModelPinMismatch`.

## Git flow (README §11)

`main` always deployable + protected; short-lived `feat/*` branches; PR → review (the other person)
→ squash-merge → delete; merge to `main` daily; CI per PR (ruff + pyright + pytest, fakes so no
Turso/Ollama/TEI). Contract changes (`core/` or API schema) → dedicated small PR both review.
