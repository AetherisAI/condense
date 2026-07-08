# API surface & schemas

The real, current HTTP contract as of `main` (2026-07-08) — read `src/sift/api/{routes,v1,tokens,schemas,deps}.py`
for ground truth; this is a human-readable map of it. Historically this doc described only the original
Step-0 4-route surface (`/ingest`, `/ingest/manifest`, `/search`, `/healthz`) — it has since grown to the
full `/v1` toolbox/answer/conversations/tokens surface below. Frozen shapes still change only via a joint
contract PR (`core/`/`api/schemas.py` are co-owned).

## Auth model

Three tiers, all bearer (`Authorization: Bearer <token>`):

- **Open** — no auth. Only `GET /healthz`.
- **Any token** (`resolve_tenant`, `api/deps.py`) — the master `INGEST_TOKEN` OR any per-consumer token
  parsed from `AUTH_TOKENS` all resolve to the single PoC tenant `"default"`. Constant-time compare
  (`hmac.compare_digest`) against every candidate — a plain `==`/`dict.get` would leak timing info about
  which leading bytes matched (CWE-208). Missing/invalid token → `401` with a `WWW-Authenticate: Bearer`
  challenge.
- **Master only** (`require_master`, `api/deps.py`) — only `INGEST_TOKEN` authenticates; a valid
  per-consumer token is rejected `403` (not `401` — the caller has *a* valid token, just not the
  privileged one). Gates `/v1/tokens/*` exclusively (minting/revoking bearer credentials is a
  higher-privilege action than anything else in the API).

## Routes

| Method · path | Auth | Purpose | Response |
|---|---|---|---|
| `GET /healthz` | open | Liveness + the pinned embed model. | `HealthResponse` |
| `GET /status` | any token | Health probes for every configured dependency + the effective config, secrets redacted. | `StatusResponse` |
| `PATCH /settings` | any token | Edit an allowlisted set of tuning knobs live (rebuilds the container in place, no restart). `extra="forbid"` — anything off the allowlist → `422`. | `StatusResponse` |
| `GET /search?q=&recap=` | any token | Embed → retrieve `RETRIEVE_K` → rerank → `FINAL_K` → recap. `recap` overrides `RECAP_ENABLED` per-request. | `SearchResponse` |
| `POST /ingest` | any token | Multipart upload (`files`, optional `modified_at` form field: JSON `{filename: iso8601}`). Streamed one file at a time (bounded memory). `409` on a model-pin mismatch. | `IngestResponse` |
| `GET /ingest/manifest` | any token | The tenant's known content-hashes — backs the agent's dedup diff. | `ManifestResponse` |
| `GET /documents` | any token | One row per ingested source file. `supported=false` (not an error) if the store can't enumerate documents. | `DocumentsResponse` |
| `DELETE /documents/{source_hash}` | any token | Drop a file's chunks by content hash. `501` if the store doesn't support document admin. | `DeleteDocumentResponse` |
| `POST /v1/documents` | any token | JSON ingest of one inline text document — the non-multipart sibling of `POST /ingest`. `text` non-empty, ≤ `PARSE_MAX_CHARS` (`422` otherwise). | `IngestFileResult` |
| `POST /v1/tools/search` | any token | The toolbox's raw-retrieval primitive: embed → `store.search`. **No recap, no LLM.** `k` defaults/caps at `TOOLS_SEARCH_K`/`TOOLS_SEARCH_MAX_K`; optional `filters` (metadata equality + `since`/`until`). | `ToolSearchResponse` |
| `GET /v1/tools/documents?limit=&offset=&metadata=` | any token | Paginated document listing, optionally narrowed by a JSON `metadata` query param. | `ToolDocumentsResponse` |
| `GET /v1/tools/documents/{source_hash}/chunks` | any token | One document's chunks, ordered by `index`. | `ToolChunksResponse` |
| `GET /v1/tools/schema` | any token | Machine-readable manifest of every registered tool (OpenAI-functions form + JSON-schema form), generated FROM the live `ToolRegistry` — `PATCH /settings` never appears here (never registered as a tool). | `ToolSchemaResponse` |
| `POST /v1/answer` | any token | The reference tool-calling agent. `stream=false` → one JSON response with a full event `trace`; `stream=true` → `text/event-stream` SSE of the same event vocabulary. `grounding` (`strict`\|`hybrid`\|`open`) overrides `ANSWER_GROUNDING_DEFAULT` per-request. | `AnswerResponse` or SSE |
| `GET /v1/conversations?limit=&offset=` | any token | Past conversations, newest-updated first. | `ConversationListResponse` |
| `GET /v1/conversations/{id}` | any token | One conversation's meta + every turn (incl. persisted sources/grounding). `404` if unknown. | `ConversationDetailResponse` |
| `DELETE /v1/conversations/{id}` | any token | Delete a conversation — idempotent (200 even if unknown). | `ConversationDeleteResponse` |
| `GET /v1/tokens` | **master only** | Names of every live per-consumer token — values are NEVER returned. | `TokenListResponse` |
| `POST /v1/tokens` | **master only** | Mint a new per-consumer token, live immediately (no restart). `409` if the name is taken. | `TokenCreateResponse` |
| `DELETE /v1/tokens/{name}` | **master only** | Revoke a consumer's token, live immediately. `404` if unknown. | `TokenRevokeResponse` |

Every non-open route resolves a `tenant` at the auth dependency (PoC: any valid token → `"default"`) and
passes it into the pipelines. `ModelPinMismatch` (configured `EMBED_MODEL`/`EMBED_DIM` ≠ a tenant's stored
pin) → HTTP `409` on both ingest routes.

## Token durability (`/v1/tokens`, D69)

Minted/revoked tokens are **runtime-live only** — they mutate `Container.auth_tokens` (the same dict
`resolve_tenant` scans) in place, so a new token authenticates immediately and a revoked one stops
working immediately, no restart. The server **never writes `.env` or any file itself** (it may not even
own that file — a container, a managed host, a dev's shell export). Every mutating response instead
carries `env_line`: the complete, current `AUTH_TOKENS=name:token,...` string. It's the operator's job to
paste that into `.env` (or wherever `Settings` reads its environment from) for the change to survive a
restart; a restart with no persisted line reverts to whatever `AUTH_TOKENS` was configured at boot. A
libSQL-backed hashed token store (survives restarts with no manual copy-paste step) is the long-term fix,
deferred as a follow-up.

## Response schemas (`api/schemas.py`, abbreviated — see the file for full docstrings)

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

class DocumentSummary(BaseModel):           # one row of GET /documents, /v1/tools/documents
    path: str
    source_hash: str
    chunks: int
    modified_at: str | None = None          # the source file's true last-modified time (D28/D44)
    indexed_at: str | None = None

class DocumentsResponse(BaseModel):         # GET /documents
    tenant: str
    documents: list[DocumentSummary]
    supported: bool = True                  # false if the store can't enumerate documents

class Source(BaseModel):                    # one citation
    path: str
    page: int
    score: float
    snippet: str = ""
    index: int | None = None
    metadata: dict[str, str] | None = None

class SearchResponse(BaseModel):            # GET /search → {summary, sources}
    summary: str
    sources: list[Source]

class HealthResponse(BaseModel):            # GET /healthz
    status: str = "ok"
    embed_model: str | None = None

class ComponentHealth(BaseModel):           # one entry of StatusResponse.components
    status: str                             # "ok" | "down" | "not_configured"
    model: str | None = None
    detail: str | None = None

class StatusResponse(BaseModel):            # GET /status, PATCH /settings
    status: str = "ok"
    embed_model: str | None = None
    components: dict[str, ComponentHealth] = {}
    settings: dict[str, Any]                # every Settings field; secrets → "set" | None

class SettingsPatch(BaseModel):             # PATCH /settings body — extra="forbid"
    recap_enabled: bool | None = None
    recap_context_k: int | None = None
    recap_max_tokens: int | None = None
    recap_temperature: float | None = None
    source_snippet_chars: int | None = None
    retrieve_k: int | None = None
    final_k: int | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    chunk_tokenizer: Literal["auto", "bge-m3", "tiktoken"] | None = None
    rerank_strategy: Literal["none", "llm", "crossencoder"] | None = None

class ToolSearchRequest(BaseModel):         # POST /v1/tools/search body
    query: str
    k: int | None = None
    filters: ToolSearchFilters | None = None  # {metadata, since, until}

class ToolSearchHit(BaseModel):             # one hit in ToolSearchResponse
    text: str
    source_path: str
    page: int
    source_hash: str
    index: int
    score: float
    modified_at: str | None = None
    metadata: dict[str, str] | None = None

class AnswerRequest(BaseModel):             # POST /v1/answer body
    message: str
    conversation_id: str | None = None
    format: Literal["text", "json"] = "text"
    json_schema: dict[str, Any] | None = None
    stream: bool = False
    grounding: Literal["strict", "hybrid", "open"] | None = None

class AnswerResponse(BaseModel):            # non-streaming POST /v1/answer response
    answer: str
    format: Literal["text", "json"]
    conversation_id: str
    trace: list[dict[str, Any]]             # full event log minus answer_delta
    truncated: bool
    sources: list[Source] = []
    grounding_used: Literal["strict", "hybrid", "open"] = "strict"
    from_general_knowledge: bool = False
    grounding_segments: list[GroundingSegment] = []  # [{text, kind: "grounded"|"general_knowledge"}]

class TokenCreateResponse(BaseModel):       # POST /v1/tokens — the ONLY place a token value appears
    name: str
    token: str
    env_line: str                           # "AUTH_TOKENS=name1:token1,name2:token2" — paste into .env
```

The route layer maps the domain `Hit`/`Chunk` (`core/types.py`) → `Source`/`ToolSearchHit`/`ToolChunk`,
and the ingest pipeline's `IngestOutcome` (`pipelines/ingest.py`) → `IngestFileResult`. Since PR #25
(D72), `pipelines/search.py` itself returns a stdlib-only `core.types.SearchOutcome`/`SearchSource` pair
(no `api.schemas` import from a pipeline — the dependency rule); `api/routes.py` maps that 1:1 onto the
HTTP `SearchResponse`/`Source` schemas, so the wire shape is unchanged.

## Config (env, read by `config.py::Settings`)

The canonical, mechanically-enforced list of every config key lives in **`.env.example`** — a contract
test (`tests/contract/test_config_env_parity.py`) fails CI if `Settings`, `.env.example`, and
`docker-compose.yml`'s `api` environment block ever drift apart. What follows is an orientation map, not
the source of truth:

```
STORE_BACKEND=libsql            TURSO_DATABASE_URL=        TURSO_AUTH_TOKEN=
EMBED_BASE_URL=                 EMBED_MODEL=bge-m3         EMBED_DIM=1024        EMBED_API_KEY=
RERANK_STRATEGY=none            RERANK_BASE_URL=          RERANK_MODEL=bge-reranker-v2-m3
RETRIEVE_K=30                   FINAL_K=1
LLM_BASE_URL=                   LLM_MODEL=                LLM_API_KEY=
CHUNK_TOKENIZER=auto            CHUNK_SIZE=512            CHUNK_OVERLAP=64
INGEST_TOKEN=                   AUTH_TOKENS=
```

**`RERANK_STRATEGY` default is `"none"`** (identity reranker, zero infra) — not `crossencoder`; earlier
drafts of this doc and `docs/SPEC.md` claimed `crossencoder` was the default, which was never true in
code. Pick `llm` (LLM-as-judge, zero extra infra) or `crossencoder` (TEI, needs the `tei` compose profile)
explicitly to change it.

**`CHUNK_TOKENIZER` IS a `Settings` field** (not a compose-only/decorative key): `"auto"` (default)
resolves to `bge-m3`'s own tokenizer when `EMBED_MODEL` names bge-m3, else falls back to the generic
`tiktoken` tokenizer — so pointing `EMBED_MODEL` at a different embedding model no longer silently
mis-tokenizes chunks in the wrong units. An explicit `"tiktoken"`/`"bge-m3"` always overrides the
auto-resolution (D72).

**Hard rule:** every compose port publishes to `127.0.0.1` by default (`API_HOST`/`WEB_HOST`/`TEI_HOST`
opt-in to LAN, D70) — the bearer token still gates every write and query either way. **Never**
port-forward any of these ports to the public internet.

**Chunk-size guard:** `CHUNK_SIZE ≤ min(embedder context, reranker max input ≈1024)` — see
`docs/dev-split.md` and the Dev A plan.
