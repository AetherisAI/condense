# Dev B Implementation Roadmap — Condense (retrieve · rank · recap · serve · UI)

> **For agentic workers:** each work package becomes a `feat/<slice>` branch with a full plan in `docs/active/machine.md` (use superpowers:writing-plans → subagent-driven-development). Steps use checkbox syntax. Living doc — not archived.

**Goal:** Build Dev B (the "surface") of Condense — embed a query, retrieve a wide candidate set from the vector store, rerank to the single best result, optionally recap it, and serve it over an authenticated FastAPI + a React test UI, all containerized.

**Architecture:** Strict ports & adapters. Pipelines compose ports only; `factory.py` is the one composition root that reads typed config and wires adapters (fakes by default). Every brick is independently testable against fakes, so Dev B never blocks on Arthur's engine.

**Tech stack (verified Jun 2026):** Python 3.13 · FastAPI 0.128 (lifespan DI) · pydantic-settings 2.14 · `openai`/`httpx` clients at custom `base_url` · TEI `/rerank` · libSQL (consumed via port) · React + Vite 7 (TS) · ruff + pyright + pytest · Docker `python:3.13-slim` multi-arch.

## Global Constraints (apply to every task)
- **P1 ports & adapters / P2 config-driven** — no adapter imports in `pipelines/`/`core/`; no hardcoded values, all via `Settings`.
- **Dependency rule:** `adapters/`→`core`; `pipelines/`→`core` ports only; `api/`→pipelines+factory; `core/`→nothing.
- **`tenant` is a parameter on every store call + pipeline + route** (PoC value `"default"`), resolved once at auth.
- **Model-pin:** embedding dim is fixed (bge-m3 = **1024**); assert `len(vector)==1024`; search/ingest refuse on `EMBED_MODEL` mismatch.
- **Auth from day 1; localhost-only PoC.** One multi-arch image, no torch.
- **TDD, frequent commits, docs ship with code.** Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## 1. Component map (the lego we build)
```
core/            types.py · ports.py                  [co-owned — we propose]
adapters/
  embedding/     openai_compat.py · fake.py
  rerank/        null.py · llm_judge.py · crossencoder_http.py(opt)
  llm/           openai_compat.py · null.py
  store/         fake.py                               [we build the fake; Arthur builds libsql.py]
pipelines/       search.py
api/             main.py · routes.py · deps.py · schemas.py
config.py · factory.py
web/             Vite+React (Search + Ingest panels)
Dockerfile · web/Dockerfile · web/nginx.conf · docker-compose.yml · .env.example
```

## 2. Port signatures (README §66–74) — the contract we build against
```python
Embedder.embed(texts: list[str]) -> list[Vector]              # Vector = list[float], len 1024
Reranker.rerank(query: str, candidates: list[Hit]) -> list[Hit]   # reordered; caller takes FINAL_K
Completer.complete(system: str, user: str) -> str             # recap rides on this
VectorStore.ensure_ready(model: str, dim: int) -> None
VectorStore.upsert(chunks: list[Chunk]) -> None
VectorStore.search(vector: Vector, k: int, tenant: str) -> list[Hit]
VectorStore.known_hashes(tenant: str) -> set[str]
# Parser/Chunker are Arthur's; we never call them directly.
```
Types: `Vector = list[float]`; `Hit{ id:str, text:str, path:str, page:int|None, score:float }`; `Chunk{ id, text, path, page, content_hash, tenant, embedding:Vector|None }`.

## 3. Integration contract with Arthur (the engine)
- **We consume** the `VectorStore` port (`search`, `ensure_ready`, `known_hashes`) — never his `libsql.py` directly. Tests use `adapters/store/fake.py`.
- **Shared seam:** `core/` (types+ports), `api/schemas.py`, and `factory.py` wiring. Treat changes as joint; **fetch `origin` every work package** and reconcile drift immediately.
- **`/ingest` route** (Dev B) delegates to `pipelines/ingest.py` (Arthur). Until his pipeline lands, the route is wired to a fake/stub behind the same `IngestPort`-shaped call so the UI + auth can be built and tested.
- **Integration point (M5):** in `factory.py` swap `FakeVectorStore` → his `LibSQLStore`, run the joint smoke test.

---

## 4. Work packages

> Each: **Goal · Owns · Interfaces (Consumes/Produces) · Depends · Build-against · Tasks · Acceptance · Docker.** Full code-level plan is written into `docs/active/machine.md` when the WP becomes active.

### WP0 — Contracts & fakes  `feat/contracts`  *(active now)*
- **Goal:** Freeze the interfaces Dev B builds against; ship the fakes that unblock all testing. Propose `core/`; align with Arthur.
- **Owns:** `core/types.py`, `core/ports.py` (Protocols), `api/schemas.py`, `adapters/embedding/fake.py`, `adapters/store/fake.py`, `adapters/rerank/null.py`, `docker-compose.yml` skeleton, `pyproject.toml`/`requirements.txt`, `tests/` bootstrap.
- **Produces:** all port Protocols + types + schemas + `FakeEmbedder` (deterministic vectors), `FakeVectorStore` (in-memory cosine search), `NullReranker` (identity).
- **Depends:** nothing. **Build-against:** n/a. **Docker:** compose skeleton (`api`,`web` services stubbed).
- **Acceptance:** `pytest` green on fakes; `FakeVectorStore.search` returns cosine-ranked Hits; ports import-clean (no cycles); ruff+pyright pass.
- *Full plan: `docs/active/machine.md`.*

### WP1 — Config & factory  `feat/config-factory`
- **Goal:** Typed `Settings` (single source of values) + `build_container(settings)` composition root; app boots wired to fakes.
- **Owns:** `config.py`, `factory.py`.
- **Consumes:** ports + fakes (WP0). **Produces:** `Settings` (all README §8 keys, `RERANK_STRATEGY: Literal["none","llm","crossencoder"]`), `get_settings()` (`lru_cache`), `build_container(s)->Container{search, ingest}` with selector dicts.
- **Depends:** WP0. **Build-against:** fakes. **Docker:** env keys surfaced in compose.
- **Acceptance:** missing required env → `ValidationError` at startup; `build_container` returns fakes by default; switching `RERANK_STRATEGY` swaps the reranker with no caller change (unit test).

### WP2 — Embedder adapter  `feat/embedder`
- **Goal:** `OpenAICompatEmbedder` behind `Embedder`.
- **Owns:** `adapters/embedding/openai_compat.py`.
- **Produces:** `embed(texts)->list[Vector]` via `openai` client (`base_url=EMBED_BASE_URL`, `api_key=EMBED_API_KEY or "x"`, `model=EMBED_MODEL`); POST `/v1/embeddings`, parse `data[].embedding`; **assert dim==1024**.
- **Depends:** WP0,WP1. **Build-against:** mocked `httpx`/recorded response. **Docker:** reaches host inference via `host.docker.internal`.
- **Acceptance:** maps a batch of texts → list of 1024-floats; raises on dim mismatch; unit test mocks the HTTP layer (no live Ollama). *Gotcha: use `/v1/embeddings` not `/api/embed` (plural-keyed); model must be pulled.*

### WP3 — Completer (LLM) adapter + null recap  `feat/completer`
- **Goal:** `OpenAICompatCompleter` + `NullCompleter` behind `Completer`.
- **Owns:** `adapters/llm/openai_compat.py`, `adapters/llm/null.py`.
- **Produces:** `complete(system,user)->str` via `chat.completions.create`, returns `choices[0].message.content`; `NullCompleter.complete` returns the user text verbatim (recap-off path).
- **Depends:** WP0,WP1. **Build-against:** mocked client. **Acceptance:** completer returns model text; null returns input unchanged; both selected by config.

### WP4 — Reranker: llm-judge  `feat/rerank-llm-judge`
- **Goal:** `LlmJudgeReranker` behind `Reranker` (PoC default). `NullReranker` already in WP0.
- **Owns:** `adapters/rerank/llm_judge.py`.
- **Produces:** `rerank(query, candidates)->list[Hit]` — builds a numbered prompt of the top candidates (cap configurable, default ~10–12 of RETRIEVE_K to bound tokens), asks the `Completer` to pick the single most relevant **and** summarize; returns candidates reordered with the chosen Hit first (recap carried for the pipeline).
- **Depends:** WP0,WP1,WP3. **Build-against:** `FakeCompleter` returning a fixed choice. **Acceptance:** given candidates + a stub judge, the chosen Hit is first; deterministic under the fake. *(Decision D4/D5.)*

### WP5 — Search pipeline  `feat/search-pipeline`
- **Goal:** `pipelines/search.py` composing ports: `embed query → store.search(vec, RETRIEVE_K, tenant) → rerank(query, candidates) → take FINAL_K → recap → {summary, sources:[{path,page,score}]}`.
- **Owns:** `pipelines/search.py`.
- **Consumes:** `Embedder`, `VectorStore`, `Reranker`, `Completer` (all via ports). **Produces:** `search(query, tenant, k=FINAL_K)->SearchResult`.
- **Depends:** WP0,WP1 (+ real adapters at integration). **Build-against:** all fakes. **Acceptance:** with `FakeEmbedder`+`FakeVectorStore`+`NullReranker`, returns the single best result + correct path; `FINAL_K`/`RETRIEVE_K` honored; tenant filter passed through. **No adapter imports** (dependency-rule test).

### WP6 — API layer  `feat/api`
- **Goal:** FastAPI surface wired via factory; auth→tenant chokepoint.
- **Owns:** `api/main.py` (lifespan builds `Container` on `app.state`), `api/routes.py`, `api/deps.py`.
- **Produces:** `GET /search?q=&k=` → `{summary, sources[]}`; `GET /healthz` → `{status, embed_model}`; `POST /ingest` (multipart, delegates to ingest port); `GET /ingest/manifest?tenant=`. `HTTPBearer` `resolve_tenant(token)->tenant` required on protected routes (single chokepoint).
- **Depends:** WP0,WP1,WP5. **Build-against:** `TestClient` + `app.dependency_overrides`. **Docker:** `uvicorn app.api.main:app`. **Acceptance:** `/search` returns schema-valid JSON; missing/invalid bearer → 401; `/healthz` reports pinned model; tests override the container with fakes.

### WP7 — React test UI  `feat/web-ui`
- **Goal:** Vite+React+TS app: Search panel (GET `/search`) + Ingest panel (multipart POST `/ingest` with bearer).
- **Owns:** `web/` (`src/Search.tsx`, `src/Ingest.tsx`, `src/App.tsx`, `vite.config.ts`).
- **Depends:** WP6 contract (can start against `api/schemas.py` + a mock). **Build-against:** Vite dev proxy → `:8000`. **Docker:** built static served by nginx. **Acceptance:** typing a query renders `{summary, sources[]}`; file upload hits `/ingest` (no manual `Content-Type` on FormData); dev proxy works.

### WP8 — Docker & compose  `feat/docker`
- **Goal:** One-command stack.
- **Owns:** `Dockerfile` (`python:3.13-slim`, deps-layer cached, uvicorn), `web/Dockerfile` (node build → nginx), `web/nginx.conf` (SPA fallback + `/search`,`/ingest` → `api:8000`), `docker-compose.yml` (api+web; **`tei` profile**), `.env.example`.
- **Depends:** WP6,WP7. **Build-against:** `docker compose up`. **Acceptance:** `docker compose up` serves UI (`:8080`) + API (`:8000`); `api` reaches host inference via `extra_hosts: ["host.docker.internal:host-gateway"]`; multi-arch buildx succeeds.

### WP9 — Cross-encoder rerank (TEI)  `feat/rerank-crossencoder`  *(optional)*
- **Goal:** `CrossEncoderReranker` behind `Reranker`; quality/speed upgrade by config flip.
- **Owns:** `adapters/rerank/crossencoder_http.py`, `tei` compose profile.
- **Produces:** POST `RERANK_BASE_URL/rerank` `{query, texts}` → bare array `[{index,score}]` (sorted desc) → map back by `index`, reorder Hits.
- **Depends:** WP4,WP5. **Build-against:** mocked TEI response. **Docker:** `tei` service (`ghcr.io/huggingface/text-embeddings-inference:cpu-1.9 --model-id BAAI/bge-reranker-v2-m3`) behind a profile. **Acceptance:** with a stubbed `/rerank`, Hits reorder by score; `RERANK_STRATEGY=crossencoder` selects it with no pipeline change. *Gotcha: TEI = one model per container; response has no `results` wrapper.*

---

## 5. Dependency graph & order
```
WP0 ─► WP1 ─►┬─ WP2 ─┐
             ├─ WP3 ─► WP4 ─┐
             └────────────► WP5 ─► WP6 ─► WP7 ─► WP8
                                     └────────► WP9 (opt, after WP4/WP5)
```
Parallelizable after WP1: WP2 ∥ WP3. WP7 can start against schemas. WP8 skeleton lands in WP0, finalized after WP6/WP7.

## 6. Milestones
- **M0 Contracts** (WP0): fakes green, app skeleton importable.
- **M1 Search-with-fakes** (WP1+WP5+null): single best result end-to-end, no external services.
- **M2 Real inference** (WP2+WP3+WP4): search works against Ollama/Mistral; llm-judge + recap.
- **M3 API** (WP6): `/search`,`/healthz` over HTTP with auth+tenant.
- **M4 UI** (WP7): search + ingest panels in the browser.
- **M5 Compose + integrate** (WP8): `docker compose up`; swap `FakeVectorStore`→Arthur's `LibSQLStore`; joint smoke test (ingest sample folder → search → single best + path → re-run agent confirms dedup).
- **M6 Cross-encoder** (WP9, optional): TEI rerank.

## 7. Testing strategy
TDD every task. Fakes (`FakeEmbedder`, `FakeVectorStore`, `FakeCompleter`, `NullReranker`) mean unit tests need no Turso/Ollama/TEI → fast CI (ruff + pyright + pytest). Adapters: mock the HTTP layer. Pipeline: fakes only, assert composition + dependency rule. API: `TestClient` + `dependency_overrides`. Integration smoke (M5): real store + real inference, manual/scripted.

## 8. Risk register
| Risk | Mitigation |
|---|---|
| `core/` contract drift with Arthur | Fetch origin every WP; contract changes = joint small PR; fakes pin the shape. |
| LLM-judge token cost at RETRIEVE_K=30 | Cap judge candidates (~10–12); config knob; switch to crossencoder (WP9) when it bites. |
| Ollama embeddings endpoint shape | Use `/v1/embeddings` (OpenAI-keyed); assert dim==1024. |
| TEI one-model-per-container | Separate ports for embed vs rerank if both via TEI. |
| Mistral 429 rate limits | Exponential backoff; batch embedding inputs. |
| `host.docker.internal` on Linux | `extra_hosts: ["host.docker.internal:host-gateway"]` on `api` (Docker ≥20.10). |

## 9. Open questions (for Arthur / Quentin)
1. Exact `Hit`/`Chunk` field names + `api/schemas.py` shape — confirm with Arthur (co-owned `core/`).
2. `/ingest` response contract + manifest shape — align with Arthur's `pipelines/ingest.py`.
3. Citation granularity page vs section fallback (README §14 Q3) — default page-where-available.
4. Corpus profile (README §14 Q4) — affects nothing in Dev B except chunk display; informational.
