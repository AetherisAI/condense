# API surface & schemas

The HTTP contract (README §8), frozen in Step 0 as `src/sift/api/schemas.py`. Clients (the agent
and the web UI) and Dev B's routes code against this; it does not change without a joint contract PR.

## Endpoints

| Method · path | Purpose | Response |
|---|---|---|
| `POST /ingest` | Bearer auth, multipart upload (field `files`, `?tenant=`). Parse → chunk → embed → upsert. | `IngestResponse` — per-file status (indexed / skipped_dedup / failed) |
| `GET /ingest/manifest?tenant=` | Known content-hashes for the agent's dedup diff; also backs the UI doc list. | `ManifestResponse` |
| `GET /search?q=&k=` | Embed → retrieve `RETRIEVE_K` → rerank → `FINAL_K` → recap (if LLM set). With `FINAL_K=1`, the single best result. | `SearchResponse` |
| `GET /healthz` | Liveness + the pinned embed model. | `HealthResponse` |

Every request resolves a `tenant` at the auth dependency (PoC: shared token → `"default"`) and
passes it into the pipelines. `ModelPinMismatch` (configured model/dim ≠ a tenant's pinned base) → HTTP 409.

## Response schemas (`api/schemas.py`)

```python
class IngestStatus(StrEnum):
    indexed = "indexed"
    skipped_dedup = "skipped_dedup"
    failed = "failed"

class IngestFileResult(BaseModel):
    path: str
    status: IngestStatus
    content_hash: str | None = None
    chunks: int | None = None
    detail: str | None = None

class IngestResponse(BaseModel):            # POST /ingest
    tenant: str
    results: list[IngestFileResult]

class ManifestResponse(BaseModel):          # GET /ingest/manifest
    tenant: str
    hashes: list[str]

class Source(BaseModel):                    # one citation
    path: str
    page: int
    score: float

class SearchResponse(BaseModel):            # GET /search → {summary, sources}
    summary: str
    sources: list[Source]

class HealthResponse(BaseModel):            # GET /healthz
    status: str = "ok"
    embed_model: str | None = None
```

The route layer maps the domain `Hit` (`core/types.py`) → `Source`, and the ingest pipeline's
`IngestOutcome` (`pipelines/ingest.py`) → `IngestFileResult`.

## Config (env, read by `config.py`)

```
STORE_BACKEND=libsql            TURSO_DATABASE_URL=        TURSO_AUTH_TOKEN=
EMBED_BASE_URL=                 EMBED_MODEL=bge-m3         EMBED_DIM=1024        EMBED_API_KEY=
RERANK_STRATEGY=crossencoder    RERANK_BASE_URL=          RERANK_MODEL=bge-reranker-v2-m3
RETRIEVE_K=30                   FINAL_K=1
LLM_BASE_URL=                   LLM_MODEL=                LLM_API_KEY=
CHUNK_TOKENIZER=bge-m3          CHUNK_SIZE=512            CHUNK_OVERLAP=64
INGEST_TOKEN=                   API_BIND=0.0.0.0
```

**Hard rule:** private LAN + bearer token only — never exposed to the public internet.
**Chunk-size guard:** `CHUNK_SIZE ≤ min(embedder context, reranker max input ≈1024)` — see
`docs/dev-split.md` and the Dev A plan.
