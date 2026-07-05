# Toolbox + Answer (v0.2.0) — Machine Doc

> Full design + plan + implementation record. Paired with `human.md` (never one without the other).

**Status:** in-progress &nbsp;·&nbsp; **Branch:** `feat/toolbox-answer` &nbsp;·&nbsp; **Updated:** 2026-07-05

## 0. North star (read this first)

The **TOOLBOX is the product**. Search, document listing, chunk access, and the schema
manifest are deterministic, LLM-free capabilities that any consumer — Condense's own
`/v1/answer`, the future WorkyTalky brain, Arthur's modules, or a bare MCP client — can
drive with its own model. `/v1/answer` is merely the **reference consumer**: it proves the
toolbox works by running it through the configured `Completer`, and it must work against
**any** OpenAI-compatible model, not just Mistral Small.

**Vocabulary rule (enforced in code + docs):** Condense has **documents** and **chunks** —
never "memory", "remember", or "forget". Memory semantics belong to the Brain service's
interpretation layer, not to Condense. Grep for `memor` in new code before every commit in
this WP; a hit that isn't a code comment quoting this rule is a bug.

**Boundary rule (enforced in code + tests):** the `/v1/answer` pipeline may only act through
`ToolRegistry` executors. No direct `store`/pipeline calls from the answer loop. A dedicated
test asserts this (see §3).

## 1. Overview

This slice adds a deterministic, introspectable tool surface (`/v1/tools/*` + `/v1/documents`
JSON ingest) on top of the existing search/ingest pipelines, a metadata channel through
`Chunk`/`Hit`/the store, per-consumer auth, a reference tool-calling agent (`/v1/answer`) with
SSE streaming and conversation state (store-level, not product-level "memory"), a
production-hardening guardrails pack, and a Chat tab in the web UI. Existing `/search`,
`/ingest`, `/documents`, `/healthz`, `/status`, `/settings` routes are **untouched** — this is
additive, a new `/v1` prefix sits beside them.

## 2. Design

### 2.1 ToolRegistry — single source of truth for tool definitions

**New module:** `src/sift/pipelines/tools.py` (pipelines-adjacent — it composes ports, no
adapter imports, same dependency-rule tier as `search.py`/`documents.py`).

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ToolParam:
    name: str
    type: Literal["string", "integer", "number", "boolean", "object", "array"]
    description: str
    required: bool = False
    enum: list[str] | None = None
    properties: Mapping[str, "ToolParam"] | None = None   # for type == "object"
    items: "ToolParam | None" = None                       # for type == "array"

@dataclass(frozen=True, slots=True, kw_only=True)
class ToolDef:
    name: str
    description: str
    params: Sequence[ToolParam]
    executor: Callable[..., Awaitable[Any]]   # binds onto Container's pipelines

class ToolRegistry:
    def __init__(self, container: Container) -> None: ...
    def tools(self) -> list[ToolDef]: ...
    async def call(self, name: str, args: Mapping[str, Any], tenant: str) -> Any: ...
    def openai_schema(self) -> list[dict]: ...      # function-calling format
    def json_schema(self) -> dict: ...               # raw JSON Schema manifest
```

- Built once per request (or cached on `Container`) from the wired `Container` — never a
  second composition root; it *is* a thin adapter over the existing `search`/`store`/`ingest`.
- Three consumers render from the **same instance**: `/v1` REST routes call `.call(...)`
  directly per-tool; `/v1/answer`'s tool loop calls `.call(...)` from within the ReAct/native
  loop; `GET /v1/tools/schema` calls `.openai_schema()`/`.json_schema()`. A future MCP wrapper
  is a fourth thin renderer over the same registry — out of scope for this WP, but the
  registry is designed so that adding it needs no changes here.
- Tools registered in v0.2.0: `search`, `list_documents`, `get_document_chunks`. `PATCH
  /settings` is **never** registered (see §2.4) — an injected prompt must never retune
  retrieval.
- If `/v1/answer` needs a capability, it MUST first exist as a registry tool — no
  side-channel calls from the answer loop into `search`/`store` (boundary rule, §0).

### 2.2 `/v1` REST surface

New `APIRouter(prefix="/v1")` in `src/sift/api/v1.py` (or `api/routes_v1.py` — decided at
implementation time by what reads cleanest beside the existing `routes.py`), mounted in
`api/main.py` alongside the existing router. Existing `/search`, `/ingest`, `/documents`,
`/healthz` stay exactly as they are (compat).

- **`POST /v1/tools/search`** — body `{query: str, k: int | None, filters:
  {metadata: dict[str,str] | None, since: str | None, until: str | None}}`. `k` defaults to
  a new `Settings.tools_search_default_k` field, capped at `Settings.tools_search_max_k`
  (default 20). Returns top-K hits: `text`, `source_path`/`page`/`source_hash`/`index`,
  `score`, `metadata`, `modified_at`. **No LLM inside — no recap.** This is the raw retrieval
  primitive the toolbox exposes; `/search` (existing) stays the recap'd single-best endpoint.
- **`GET /v1/tools/documents`** — paginated: `limit` (default 100), `offset` (default 0),
  optional metadata-equality query filters. Returns `{documents, total, limit, offset}`.
  Built on `SupportsDocumentAdmin.list_documents` (existing seam, §2.5) plus the new metadata
  column for filtering.
- **`GET /v1/tools/documents/{source_hash}/chunks`** — ordered chunks (by `index`) of one
  document. New store method (or reuse `search` with a source_hash-equality filter — decided
  in T2 by what's cheaper against libSQL; either way it's additive, never touching
  `upsert`/`search`'s existing contract).
- **`GET /v1/tools/schema`** — machine-readable manifest of all registry tools, generated FROM
  `ToolRegistry` (never hand-written): `{openai_functions: [...], json_schema: {...}}`.
- **`POST /v1/documents`** — JSON ingest: `{text: str, filename: str | None, metadata:
  dict[str,str] | None, modified_at: str | None}` → same `IngestFileResult` shape as the
  existing multipart `/ingest`. Internally: wrap `text.encode()` as a one-file
  `Sequence[tuple[str, bytes]]` and call the same `SupportsIngest.ingest(...)`, threading
  `metadata` through (new param, §2.3). Existing multipart `/ingest` is untouched.

All `/v1/tools/*` GET/POST routes and `/v1/documents` require `resolve_tenant` (extended in
§2.4) exactly like the existing routes. `GET /v1/tools/schema` is also authenticated (it
reveals the shape of internal tools) — no unauthenticated introspection.

### 2.3 Metadata channel

**Additive, co-owned `core/types.py` — flag to Arthur (`docs/channel/from-quentin.md`).**

- `Chunk.metadata: dict[str, str] | None = None` and `Hit.metadata: dict[str, str] | None =
  None` — new fields on the existing frozen dataclasses, default `None` so every existing
  construction site (fakes, tests, Arthur's engine) keeps compiling unchanged.
- `api/schemas.py::Source` gains `metadata: dict[str, str] | None = None` (Dev-B-owned,
  no flag needed).
- **libSQL:** a `metadata` JSON `TEXT` column on the `chunks` table, added via an
  ALTER-if-missing migration — same pattern as the existing `modified_at` migration (D28).
  Stored as `json.dumps(chunk.metadata)` / parsed back with `json.loads(...) or None`.
- **Ingest threading:** `POST /ingest` (multipart) and the new `POST /v1/documents` (JSON)
  both accept an optional per-file `metadata: dict[str, str]` and thread it into
  `IngestPipeline.ingest(..., metadata: Mapping[str, dict[str, str]] | None = None)` (new
  additive param, mirroring the existing `modified_at` map-by-filename pattern from D28) →
  `dataclasses.replace(chunk, metadata=...)` on every chunk of that file.
- **Search-time filtering:** filtering happens **before** the vector-ranking `k` limit is
  applied — i.e. filters narrow the candidate set at the SQL layer (`json_extract(metadata,
  '$.key') = ?` equality, plus `modified_at` range via `since`/`until`), not as a post-hoc
  Python filter on an already-capped top-K. **Decided in T2 (D38):** an additive `filters:
  SearchFilters | None = None` parameter directly on the `VectorStore.search` port (not a
  separate Protocol) — every existing call site is unaffected (default `None`), and the raw
  retrieval tool's contract (search + filters together) is genuinely part of "what a store's
  search does," unlike the admin/chunk-access seams which stay separate Protocols. `FakeVectorStore`
  and `LibSQLStore` both implement it (the latter via `json_extract`/range SQL, **CROSS-BOUNDARY**,
  flagged in the channel per update 19). `SupportsDocumentAdmin.list_documents` gains a parallel
  additive `metadata` parameter (SQL `EXISTS` subquery in libSQL); a new `SupportsChunkAccess`
  Protocol (`get_chunks`) backs `GET /v1/tools/documents/{hash}/chunks`, mirroring
  `SupportsDocumentAdmin`'s isinstance-degrade pattern.

### 2.4 Auth — per-consumer tokens

- `Settings.auth_tokens: str = ""` — parsed as `"name1:token1,name2:token2"` into a
  `dict[str, str]` (name → token) at construction (a small validator or a cached property;
  malformed entries are dropped with a WARNING log, never a startup crash — this is a
  convenience layer on top of the existing hard-required `ingest_token`, not a replacement).
- `resolve_tenant` (extended, `api/deps.py`) accepts the existing `ingest_token` **or** any
  token in `auth_tokens`; either resolves to tenant `"default"` (unchanged single-tenant PoC
  behavior — a decision entry follows at implementation). The consumer name (from the matched
  `auth_tokens` entry, or `"ingest"` for the legacy token) is logged on every request for
  traceability — no behavior differs by consumer name yet, this is purely observability for
  the multi-consumer future.
- **`PATCH /settings` is excluded from the toolbox/schema forever** — it is never registered
  in `ToolRegistry`, never listed in `GET /v1/tools/schema`, and this exclusion gets its own
  regression test (an injected prompt reaching the tool loop must structurally be unable to
  retune retrieval, embedding, or store settings).

### 2.5 `/v1/answer` — the reference agent

- **Request:** `POST /v1/answer` `{message: str, conversation_id: str | None, format:
  "text" | "json" = "text", json_schema: dict | None, stream: bool = False}`.
- **New additive core port** `ToolCompleter` (`core/ports.py`, co-owned — flag to Arthur):

  ```python
  @runtime_checkable
  class ToolCompleter(Protocol):
      async def complete_with_tools(
          self, system: str, messages: list[dict], tools: list[dict]
      ) -> ToolCompletion: ...
  ```

  `ToolCompletion` (new `core/types.py` addition, additive) carries either a final message or
  one/more tool calls (name + args), uniformly regardless of native vs. prompted mode.
- **Implementation:** the existing `OpenAICompatCompleter` (`adapters/llm/openai_compat.py`)
  grows a `complete_with_tools` method implementing `ToolCompleter`. `Settings.answer_tool_mode:
  Literal["auto", "native", "prompted"] = "auto"`: `"auto"` tries the OpenAI-compatible
  `tools=[...]` function-calling parameter once; on an HTTP 4xx that looks like
  "tools unsupported" (or any error before a single successful call) it falls back to a
  strict-JSON prompted ReAct loop (a system prompt instructing `{"tool": ..., "args": ...}` /
  `{"final": ...}` turns, parsed defensively) for the **rest of that conversation**. `"native"`/
  `"prompted"` force one mode with no fallback (useful for tests + debugging).
- **Tool loop** (new `pipelines/answer.py`): embed→retrieve is never called directly — every
  capability the loop uses comes from `ToolRegistry.call(...)` (boundary rule, §0). Loop:
  build system prompt (tool descriptions + citation instructions) → call `ToolCompleter` →
  if tool call(s), execute via registry, append `tool_result` to the transcript, loop; if
  final message, done. Hard budgets, all `Settings`: `answer_max_tool_calls: int = 6`,
  `answer_timeout_s: float = 120.0`, `answer_max_tokens: int | None` (recap-style cap on the
  final completion). On budget exhaustion: return the best-effort answer built from whatever
  tool results were gathered, with a `truncated: bool = True` flag in the response — never a
  bare timeout/500.
- **Conversation state:** new libSQL table `conversations(conversation_id, turn_idx, role,
  content, created_at)` behind a small `ConversationStore` seam (Protocol in
  `pipelines/answer.py` or a sibling module, mirroring `SupportsDocumentAdmin`) —
  `FakeConversationStore` (in-memory dict) for tests, libSQL adapter at integration.
  `Settings.answer_history_max_turns: int = 20` and `answer_history_ttl_s: int | None` (None =
  no TTL) bound growth. `conversation_id` is generated (uuid4) on the first turn and returned
  in every response so callers thread the same conversation forward.
- **`format="json"`:** the caller supplies `json_schema`; the final-turn system prompt is
  augmented with "respond with JSON conforming to this schema" + the schema itself; the
  response is parsed with `json.loads` and validated shape-wise (best-effort — a full JSON
  Schema validator is out of scope; one retry on parse/shape failure, then a structured error
  in the response body rather than a raw string). `format="text"` (default) returns markdown
  with inline citations (`[source_path p.N]`-style, consistent with the existing recap
  citation convention in `pipelines/search.py`).
- **`stream=true`:** `text/event-stream` SSE. Event vocabulary (shared between SSE and the
  non-stream trace so the UI and any other consumer read one vocabulary):
  - `{"type": "thinking", ...}` — optional, model's own pre-tool-call reasoning if the mode
    surfaces any.
  - `{"type": "tool_call", "tool": str, "args_summary": str, "args": dict}` — `args_summary`
    is a short human string (e.g. `"unity developer CVs"`), `args` the full call.
  - `{"type": "tool_result", "tool": str, "summary": str, "detail": Any}` — `summary` e.g.
    `"8 hits"`, `detail` the actual tool return value.
  - `{"type": "answer_delta", "text": str}` — token/chunk-wise streaming of the final answer.
  - `{"type": "done", "conversation_id": str, "truncated": bool}`.
  Non-stream `POST /v1/answer` returns one JSON body: `{answer, sources, conversation_id,
  truncated, trace: [...same event shapes, minus answer_delta which collapses to the full
  answer...]}` — so a non-streaming caller still gets the full tool-use trace for
  observability/debugging, just not incrementally.

### 2.6 UI (web/)

Reuses the existing Vite+React app's design language (`web/src/App.css`, existing component
patterns in `Search.tsx`/`Ingest.tsx`/`Library.tsx`/`SystemMenu.tsx`) — **no new design
system, no new component library.**

- **Chat tab** beside the existing Search tab (`App.tsx`'s tab switcher). Message thread +
  input, mirroring `Search.tsx`'s existing fetch/loading/error patterns but hitting
  `POST /v1/answer` with `stream: true` via a manual `fetch` + `ReadableStream` reader
  (browser `EventSource` can't set an Authorization header, so a manual SSE reader over
  `fetch` is used, matching how `Ingest.tsx` already handles bearer auth on `fetch`).
- **Activity timeline:** while the agent runs, each SSE event renders as one stylized line —
  a small icon per event type (search icon + `"Searching: <args_summary>"`, then
  `"→ 8 hits"`) with a subtle pulse animation on the currently-active line (CSS, no new
  dependency). Each line has a chevron that expands to the full `args`/`detail` JSON
  (collapsed by default) — a quiet progress narrative, not a log dump. Final answer renders in
  the existing Answer-card style (reusing `Search.tsx`'s result-card CSS classes) with sources
  listed the same way search results are today.
- **System menu → Settings section:** an editable panel driven by the existing
  `GET /status` + `PATCH /settings` (already-shipped `SettingsPatch` allowlist,
  `SystemMenu.tsx` already exists — extend it, don't replace it). Group fields (recap /
  retrieval / rerank / chunking) each with a one-line explanation (reuse `Settings`'s own
  field docstrings/comments as the copy source where practical); live-tunable fields (the
  existing `SettingsPatch` allowlist) are inline-editable with a save-via-`PATCH` action;
  restart-required fields (model pins, base URLs, store backend) render read-only/greyed with
  a "restart required" hint — sourced from `GET /status`'s existing `settings` dict, simply
  partitioned into editable vs. read-only by whether the field is in `SettingsPatch`.

### 2.7 Config policy

**One canonical `.env`** — `.env.example` lists **every** `Settings` field (existing +
new), grouped into commented sections matching the spec: `STORE` / `EMBEDDING` / `RERANK` /
`LLM+ANSWER` / `OCR` / `PARSING GUARDS` / `INGEST+AUTH` / `UI-SURFACED`. Every key gets a
one-line explanatory comment (matching the existing style already in `.env.example`).
`docker-compose.yml` env passthrough stays in parity — every new `Settings` field appears
there too. No scattered config anywhere (P2) — every new tunable in this WP becomes a
`Settings` field, no exceptions, including the guardrails in §2.8.

### 2.8 Guardrails pack (production messiness)

All additive, all `Settings`-driven, all independent of each other (any one can land without
the others):

- **`parse_max_chars: int = 2_000_000`** — a generic post-parse extracted-text ceiling for
  *all* formats (defense-in-depth alongside D34's xlsx-specific pre-parse cell guard, which
  stays as the primary fix for that specific failure shape). A `Document`/`Page` whose total
  text exceeds this raises an explicit `ParseError` — never silent truncation.
- **`parse_timeout_s: float = 60.0`** — per-file wall-clock timeout wrapping the existing
  `asyncio.to_thread(...)` parse call in `asyncio.wait_for(...)`; a hung parse (e.g. a
  pathological format the guard above doesn't catch) fails that one file explicitly instead of
  stalling the whole ingest batch.
- **`scripts/run-engine.sh`** gains `-p Restart=on-failure -p RestartSec=2` on its
  `systemd-run` invocation — an engine that's cgroup-OOM-killed (D29/D34's containment) now
  restarts itself instead of staying down.
- **Agent collect exclude-file-patterns:** `agent/sync.py`'s existing `DEFAULT_EXCLUDE_DIRS`
  (D35/R4) gains a sibling `DEFAULT_EXCLUDE_FILES` (glob-style: `MEMORY.md`, `CLAUDE.md`,
  `*.tmp`, extendable) filtering individual filenames the same way directories are pruned —
  closes the Acme-corpus finding where agent-internal bookkeeping files polluted the index.
  Configurable the same way as `exclude_dirs` (`AgentConfig.exclude_files`, `--exclude-file`
  CLI flag). **CROSS-BOUNDARY** — edits Arthur-owned `agent/` files, same basis as D25/D29/
  D32/D34/D35 (Quentin's explicit direction); flagged in the channel update.
- **`docker-compose.yml`:** `TURSO_DATABASE_URL` default `file:/data/sift.db`, a named volume
  `sift-data` mounted at `/data`, a `healthcheck` on `/healthz`, and `mem_limit` for the `api`
  service (a compose-level ceiling mirroring this session's own `systemd-run` discipline,
  D29/D34) — so a fresh `docker compose up` gets a working embedded-replica DB path and a
  memory ceiling with zero manual setup.

## 3. Boundary + vocabulary enforcement (concrete tests)

- `tests/pipelines/test_answer_boundary.py` (new): assert that `pipelines/answer.py` imports
  no `sift.adapters.*` module and never touches `Container.store`/`Container.search`
  directly — every capability flows through `ToolRegistry.call(...)`. Exact mechanism (AST
  inspection of the module's imports vs. a runtime double that raises on out-of-band access)
  decided in T3; the test must fail red if a future edit adds a direct
  `container.store.search(...)` call to the answer loop.
- `tests/pipelines/test_tools_schema.py` (new): `GET /v1/tools/schema` (or the registry's
  `.openai_schema()`/`.json_schema()` directly) never contains an entry named `settings` or
  anything mapping onto `SettingsPatch` fields.
- A repo-wide grep-based test (lightest touch: a single pytest that greps `src/sift/**/*.py`
  for `\bmemor(y|ies)\b` case-insensitive outside of comments referencing *this rule itself*)
  enforces the vocabulary rule mechanically, not just by convention — exact allowlist decided
  in T1 so it doesn't false-positive on this doc or on legitimate third-party terms.

## 4. Plan (writing-plans format)

> Checkbox tasks, TDD, commit per task. Build order: **T1 foundations → T2 toolbox/v1+auth →
> T4 guardrails/env hygiene → T3 answer agent+SSE → T5 UI → E2E acceptance.** T4 is pulled
> before T3 deliberately — the guardrails are independent, low-risk, and unblock a stable
> engine before the higher-complexity agent loop lands on top of it.

### T1 — Foundations: metadata channel + JSON ingest
**Files:** `core/types.py` (Chunk/Hit.metadata), `api/schemas.py` (Source.metadata,
`DocumentIngestRequest`), `pipelines/ingest.py` interface note (additive `metadata` param —
Arthur's file, flag only), `adapters/store/fake.py` (metadata round-trip), `api/routes.py`
(new `POST /v1/documents`), tests throughout.
- [x] `Chunk`/`Hit` gain `metadata: dict[str, str] | None = None`; existing construction call
      sites across the suite still pass (no signature break — TDD: write a test constructing
      `Chunk()`/`Hit()` with no `metadata` arg first, confirm it's already green post-add).
      **Landed 2026-07-04:** also threaded through `pipelines/ingest.py` (additive `metadata`
      param, mirrors the `modified_at` per-filename map, D28), `adapters/store/libsql.py`
      (new `metadata TEXT` column + ALTER-if-missing migration mirroring the `modified_at`
      one), and `pipelines/search.py` (`Source.metadata = hit.metadata`). See D37.
- [x] `FakeVectorStore` round-trips `metadata` through `upsert`→`search` (failing test first).
      Also covered against libSQL (`tests/adapters/store/test_libsql_store.py`, incl. a legacy
      pre-``metadata``-column database migrating cleanly).
- [x] `POST /v1/documents` JSON-ingest route + schema (new `api/v1.py`, mounted beside the
      existing router); failing test posts `{text, filename, metadata}`, expects an
      `IngestFileResult` (returned directly, not the multipart route's list-wrapping envelope
      — see D37). Empty `text` → 422 via `Field(min_length=1)`; dedup on identical text
      covered; default `filename` (`note-<hash8>.txt`) covered.
- [ ] Metadata-equality filter seam decision recorded (Protocol vs. port extension) +
      `FakeVectorStore`-level filter support with a failing-first test. **Not landed this
      pass** — deferred, see D37's "filter seam deferred" note; this task's assigned scope was
      storage/threading/surfacing + the JSON ingest route only.
- [ ] `since`/`until` (`modified_at` range) filter support, same seam, failing-first test.
      **Not landed this pass** — same deferral as above.
- [x] Decision logged in `DECISIONS.md` (D37); commit.

### T2 — Toolbox `/v1` + per-consumer auth
**Files:** `pipelines/tools.py` (new), `api/v1.py` (new router), `api/deps.py` (extended
`resolve_tenant`), `config.py` (`auth_tokens`, `tools_search_k`, `tools_search_max_k`),
`factory.py` (`Container.tools`/`auth_tokens`), `core/ports.py` (`VectorStore.search` gains
additive `filters`), `core/types.py` (`SearchFilters`), `pipelines/documents.py`
(`SupportsDocumentAdmin.list_documents` gains additive `metadata`; new `SupportsChunkAccess`),
`adapters/store/fake.py` + `adapters/store/libsql.py` (filters/metadata-filter/`get_chunks`,
**CROSS-BOUNDARY** on the libSQL file — flagged in the channel per update 19).
- [x] `ToolRegistry` (`ToolSpec`/`ToolRegistry`, `.tools()`) with `search`/`list_documents`/
      `get_document_chunks` registered; tests assert `.tools()` shape
      (`tests/pipelines/test_tools.py`).
- [x] `ToolRegistry.call("search", ...)` executes embed→`store.search` with no recap (raw hits);
      covers `k` default (`Settings.tools_search_k`) and cap (`Settings.tools_search_max_k`) and
      `filters` (metadata equality + `since`/`until`).
- [x] `list_documents` (paginated + `total`, optional metadata filter) + `get_document_chunks`
      (ordered by `index`) tools registered + executable; both degrade gracefully (empty) when
      the store doesn't implement the seam.
- [x] `.to_openai_functions()` / `.to_json_schema_manifest()` generated from the registry;
      `tests/pipelines/test_tools_schema.py` asserts a `settings`-like tool/field is structurally
      absent from either render (ties into §3's schema test) — also covers the deferred
      vocabulary-rule grep test (`tests/contract/test_vocabulary_rule.py`, D37's note).
- [x] `POST /v1/tools/search`, `GET /v1/tools/documents`, `GET /v1/tools/documents/{hash}/
      chunks`, `GET /v1/tools/schema` routes wired to the registry; `TestClient` tests per route
      (auth required, shape asserted) in `tests/surface/api/test_v1_tools.py`.
- [x] `Settings.auth_tokens` parsing (`"name:tok,name2:tok2"` → `{token: name}`, malformed
      entries dropped+logged) — `parse_auth_tokens`, unit tests in `test_config.py`.
- [x] `resolve_tenant` accepts any `auth_tokens` value or the legacy `ingest_token`; logs the
      consumer name at INFO; tests per branch (legacy token, two named tokens, unknown token →
      401, missing token → 401) in `tests/surface/api/test_auth.py`.
- [x] Full `/v1` route suite green (283/283) + ruff clean; commit. Decision logged: D38.

### T4 — Guardrails + env hygiene
**Files:** `adapters/parsing/markitdown.py` (or a shared post-parse hook), `config.py`
(`parse_max_chars`, `parse_timeout_s`), `scripts/run-engine.sh`, `agent/sync.py`+`config.py`+
`cli.py` (exclude-files), `docker-compose.yml`, `.env.example`.
- [x] `parse_max_chars` ceiling + explicit `ParseError`; failing test (oversized `Document`
      text → `ParseError`, under-limit unaffected). **Landed** (commit `c21819b`).
- [x] `parse_timeout_s` wall-clock guard around the parse call; failing test (a
      slow/hanging fake parser → explicit timeout failure, fast parser unaffected). **Landed**
      (commit `c21819b`).
- [x] `scripts/run-engine.sh` gains `Restart=on-failure`/`RestartSec=2`; verified by inspection
      (shell script, no unit test — note in the implementation log). **Landed** (commit `dbc1e77`).
- [x] `DEFAULT_EXCLUDE_FILES` + `AgentConfig.exclude_files` + `--exclude-file`; failing tests
      mirroring the existing `DEFAULT_EXCLUDE_DIRS` coverage (D35/R4) — flagged cross-boundary.
      **Landed** (commit `dbc1e77`).
- [x] `docker-compose.yml`: `TURSO_DATABASE_URL` default + `sift-data` volume + `/healthz`
      healthcheck + `mem_limit`; verified by `docker compose config` (no live daemon needed).
      **Landed** (commit `6c9097a`).
- [x] `.env.example`/`docker-compose.yml` env parity for T2's `TOOLS_SEARCH_K`/
      `TOOLS_SEARCH_MAX_K`/`AUTH_TOKENS` and T4's own `PARSE_MAX_CHARS`/`PARSE_TIMEOUT_S`.
      **Not landed with the T4 commits above** (their own commit messages note this was
      deferred) — landed as a drive-by during T3 (D40) rather than left inconsistent; the
      broader `EMBED_*`/`OCR_*`/`RECAP_*` env-parity gap in `docker-compose.yml` is still
      open, flagged in the channel.
- [x] Full suite green + ruff + pyright; commit. **Retroactive note (D40):** T4's three
      commits (`c21819b`/`dbc1e77`/`6c9097a`) landed without their `DECISIONS.md` entry in the
      same commit (CLAUDE.md §6) — backfilled as **D39** while landing T3.

### T3 — `/v1/answer` reference agent
**Files:** `core/ports.py` (`ToolCompleter`), `core/types.py` (`ToolCompletion`),
`adapters/llm/openai_compat.py` (`complete_with_tools`), `pipelines/answer.py` (new),
`config.py` (answer_* settings), `api/v1.py` (`POST /v1/answer` incl. SSE), conversation store
seam + fake + libSQL adapter.
- [x] `ToolCompletion`/`ToolCompleter` port defined; `FakeToolCompleter` (scripted responses,
      no live LLM) added for tests — every LLM-dependent test in this WP uses it.
      `messages`/`tools`-only signature (system folded into `messages[0]`), a deliberate
      deviation from this doc's original sketch — see D40.
- [x] Native tool-calling path on `OpenAICompatCompleter.complete_with_tools`; failing test
      against a mocked HTTP response with a `tool_calls` payload.
- [x] Prompted-JSON fallback path (`answer_tool_mode="prompted"`); failing test with a scripted
      completer emitting `{"tool":...}`/`{"final":...}` turns. Also flattens the transcript's
      native-shaped tool exchanges into plain turns first (D40) — not in the original sketch.
- [x] `auto` mode: native attempt → fallback on failure, sticky for the rest of the
      process (not just "the conversation" — the completer instance's whole lifetime, D40);
      failing test simulates a native-call HTTP error then a successful prompted turn, then
      asserts a SECOND call never retries native.
- [x] Tool loop (`pipelines/answer.py`) drives `ToolRegistry` only (boundary-rule test from §3
      written FIRST, red, then the loop implemented to make it green — this is the one task in
      the plan where the enforcement test predates the feature it constrains).
      `tests/pipelines/test_answer_boundary.py`.
- [x] Hard budgets: `answer_max_tool_calls`, `answer_timeout_s`, `answer_max_tokens`; each has
      its own failing-first test (a `FakeToolCompleter` that would loop forever without the
      cap; a slow fake that would exceed the timeout) proving graceful truncation, never a
      raw error/hang. `answer_max_tokens` wired as its OWN completer param, separate from
      `recap_max_tokens` (D40) — the original sketch didn't call this out and it would have
      silently aliased the two.
- [x] Conversation store seam + `FakeConversationStore`; `conversation_id` round-trip test
      (two turns, second turn's context includes the first). ALSO landed (beyond this task's
      minimum): a real `LibSQLConversationStore` adapter (own connection, same async-over-sync
      shape as `LibSQLStore`) with its own `tmp_path`-backed test suite — a turn-numbering bug
      (`COUNT(*)` colliding with a surviving row's PK after the ring-buffer trim first fires)
      was caught by TDD and fixed via `MAX(turn) + 1` before landing (D40).
- [x] `format="json"` + `json_schema` constrained output + one retry on parse failure; failing
      test with a scripted malformed-then-valid completer response.
- [x] SSE (`stream=true`) emits the documented event vocabulary in order; failing test reads
      the `text/event-stream` body via `TestClient` and asserts event types/ordering.
- [x] Non-stream response includes the same trace shape; failing test.
- [x] Full suite green + ruff + pyright; commit. Decision(s) logged in `DECISIONS.md` (D40:
      native-vs-prompted fallback heuristic, `ToolCompleter` signature deviation, conversation
      turn-numbering fix, `answer_max_tokens` separation; D39 backfilled for T4).

### T5 — UI: Chat tab + activity timeline + Settings section
**Files:** `web/src/App.tsx` (tab), `web/src/Chat.tsx` (new), `web/src/SystemMenu.tsx`
(extended), CSS additions to `web/src/App.css` (no new design system).
- [x] `Chat.tsx`: message thread + input, `POST /v1/answer` with `stream:true` from the start
      (the non-streaming path was superseded — a scripted `ToolCompleter`-backed harness gave a
      real backend to drive during manual verification, see the implementation log entry below).
- [x] SSE reader (`fetch` + `ReadableStream`, bearer header, `\n\n`-delimited `data:` frames);
      activity timeline renders each `tool_call`/`tool_result` pair as one quiet line (icon +
      human phrasing + `· N hits` once resolved) with a pulse while in flight and a chevron
      expanding the raw args/result JSON (collapsed by default).
- [x] Final answer renders in the existing Answer-card style (`.recap` markdown) with sources —
      citations are pulled from any `search` tool results seen along the way (deduped by
      path+page, best score first), same `.source`/`.badge`/`.snippet` markup Search.tsx uses.
      The timeline collapses to one summarized line ("N searches · M listings — expand") once
      the turn finishes.
- [x] `SystemMenu.tsx` Settings section: settings grouped to mirror `.env.example`'s sections
      (Store/Embedding/Rerank/Retrieval & recap/LLM & answer/OCR/Parsing guards/Ingest & auth),
      each key given a one-line explanation (reusing the existing mode-info hover-tooltip
      pattern); the `SettingsPatch` whitelist stays inline-editable with an optimistic "Saved ✓"
      fade on a successful `PATCH /settings`; model/URL/store/token keys are greyed with a
      "restart" badge (`title` hint) since `factory.py` only rewires them at container-build
      time. Any settings key not yet bucketed into a group still renders under "Other" so
      nothing silently disappears.
- [x] Manual smoke: `npm run build`/`npm run lint` clean (2G-capped scope); a dedicated dev
      instance (`sift-web-wp2`, port 5174) run against a real backend (see below) — genuinely
      screenshotted via a locally-launched headless Chrome (the `claude-in-chrome` MCP tools
      were not reachable from this subagent session), never against the production
      `sift-web`/`sift-engine` units. Since the production engine (`:8000`) was down for the
      whole of this pass (pre-existing, unrelated — confirmed no command in this session
      referenced it), a throwaway scratchpad harness (`e2e_harness.py`, NOT committed) served
      the real `sift.api.main:app` on `:8001` with fakes/nulls everywhere except a scripted
      `ToolCompleter` standing in for the LLM (same pattern as the test suite's
      `FakeToolCompleter`) — genuine `ToolRegistry`/`AnswerPipeline`/SSE code paths, only the
      "model" is canned. Verified: Search baseline, System panel (grouped + tooltip + restart
      badges + Saved✓ feedback), Chat idle/thinking/active-search/answered/timeline-expand/
      detail-expand — ten-plus screenshots, judged calm and native to the app, not a log dump.

### E2E — Acceptance (against the Acme corpus, real LLM)
- [x] (a) `/v1/answer` "What people profiles and their CV's do we have? List them all" →
      enumerates ALL people (~12 across 50 docs), not 2. **Re-verified 2026-07-04 (bugfix
      round, D40 amendment): still `truncated: true` even after `answer_max_tool_calls` 6→10**
      — `list_documents` (50 of 50) + 9 rounds of `get_document_chunks` exhausts the budget
      before a final enumeration. NOT fixed at that point; needed a different strategy, not a
      bigger budget. **Fixed this pass (D41):** explicit strategy guidance in `_SYSTEM_PROMPT`
      + the three tool descriptions (`list_documents` ALONE is authoritative for enumeration;
      `get_document_chunks` never for whole-corpus iteration). **Re-verified live 3/3 — all
      `truncated: false`, all 14 people/CVs enumerated every run**, never touching
      `get_document_chunks`. See D41.
- [ ] (b) Follow-up in the same `conversation_id` "But there are other CV's too look closely"
      → uses conversation context, surfaces more/correct people. Not exercised this pass.
- [x] (c) An ambiguous query triggers visible multi-tool probing (multiple `tool_call`/
      `tool_result` events) with citations in the final answer. **Re-verified 2026-07-04:**
      "who would fit a creative XR project?" → **200 on 2/2 attempts** (was reproducibly 500ing
      before this pass's BUG #2 fix — Mistral's multi-cited answer came back as a content-block
      LIST, not a string, and crashed the conversation store), substantive cited answer each
      time (e.g. `(Hiring/Jordan-Rivera.pdf, p.1)`), `truncated: false`. One `tool_call`/
      `tool_result` pair observed each time, not the originally-envisioned "multiple" — the
      model resolved it in a single `search` round both times, which is a legitimate outcome,
      not a failure of this checklist item's intent (citations + a genuine tool round-trip both
      present).
- [ ] (d) `format=json` with a caller-supplied schema returns schema-conforming extraction. Not
      exercised this pass.
- [x] Results + any follow-up fixes captured in the implementation log below before the WP is
      considered ready to archive. See the 2026-07-04 bugfix-round entry below and
      `DECISIONS.md`'s D40 amendment.

### T6 — Chat UX fixes: answer-in-focus + conversation persistence/history (P1/P2)
**Trigger:** Quentin's live use of the Chat tab (`:5174` against `sift-engine-wp2`, real Mistral)
surfaced two pains — (P1) a follow-up's full source cards pushed the answer out of view above
them; (P2) Chat → Search → Chat lost the conversation with no way to browse past ones.
**Files:** `core/types.py`, `config.py`, `pipelines/answer.py`, `adapters/conversation/
{fake,libsql}.py`, `adapters/llm/fake.py` (new `FakeCompleter`), `factory.py`, `api/{schemas,v1}.py`,
`web/src/Chat.tsx`, `web/src/ChatHistory.tsx` (new), `web/src/App.css`.

- [x] `ConversationTurn.sources` (additive) + new `ConversationMeta`/`ConversationDetail`
      dataclasses (`core/types.py`, stdlib-only, mirrors `ConversationTurn`/`DocumentInfo`).
- [x] `ConversationStore` port widened (`pipelines/answer.py`): `append_turn(..., sources=)`,
      `set_title_if_unset`, `list_conversations`, `get_conversation`, `delete_conversation` —
      implemented in both `FakeConversationStore` and `LibSQLConversationStore` (new
      `conversations_meta` table + additive `sources` column, both ALTER-if-missing migrated,
      `_ensure_schema` run at the top of every job incl. reads); failing tests first for every
      method in both stores, incl. a hand-built legacy-schema self-heal test.
- [x] Tool loop accumulates `search` hits into a compact citation list (`_merge_sources` — dedup
      by path+page, snippet ≤200 chars, capped 6, best-first) and emits `{"type":"sources",
      "items":[...]}` just before `done` (SSE + non-stream trace, same vocabulary); persisted onto
      the assistant's own turn. `AnswerResponse` gains a top-level `sources` convenience field.
- [x] Auto-title: after the first assistant answer, one extra `Completer.complete()` call (a new
      optional `title_completer` param, separate from `tool_completer` since `FakeToolCompleter`
      implements only `complete_with_tools`) produces a 5-8 word title, stored once via
      `set_title_if_unset`; any failure (no completer / HTTP error / empty reply) falls back to
      the first user message truncated to 60 chars. `Settings.answer_autotitle_enabled` (default
      `true`); `factory.py` wires `title_completer=completer` — the SAME instance as the recap,
      so it's budget-capped via `recap_max_tokens`/`recap_temperature` with no new knob.
- [x] `GET /v1/conversations` (list, newest-updated first), `GET /v1/conversations/{id}` (meta +
      turns incl. persisted sources), `DELETE /v1/conversations/{id}` (idempotent) — plain REST
      over the new `Container.conversations`, deliberately NOT `ToolRegistry` tools (D42); a
      standing regression test pins the registry to exactly the 3 corpus tools.
- [x] `Chat.tsx`: DOM order per exchange is now user bubble → answer (always) → collapsed
      `N sources · expand` pill (`.tl-summary`-styled) → the activity timeline's own collapsed
      pill — no full source wall by default; expanding shows compact cards (filename/page/match %,
      3-line-clamped snippet, its own "Show more"). Auto-scroll now tracks a `pinnedToBottomRef`
      toggled by the thread's own `onScroll` (≈48px-from-bottom threshold) instead of
      unconditionally jumping to `scrollHeight` on every state change.
- [x] P2: `conversation_id` persists to `localStorage`, refetched (`GET /v1/conversations/{id}`)
      on mount — Chat fully unmounts when the Search tab is active, so this is simpler than
      lifting state into `App.tsx` (matches the task's own steer). New `ChatHistory.tsx`
      (Library-drawer-styled): lazy-fetched on open, past conversations by title/relative-time,
      current one highlighted, click-again-to-confirm delete, click a row to reopen+continue.
- [x] `npm run build` / `npm run lint` clean; backend suite 396/396 green (was 349; +47) in a
      2G-capped scope; `ruff check`/`ruff format --check` clean; `pyright` unchanged in kind
      (one new same-category `test_routes.py` error, D38/D40's documented 1-field-1-error scaling).
- [x] Live re-verify (real Mistral via `sift-engine-wp2` restart on `:8001`, real `sift-web-wp2`
      on `:5174`, headless Chrome via `playwright-core`): answer-in-focus + sources collapsed,
      expand → compact cards, a follow-up keeps the same ordering (no scroll-trap), Search↔Chat
      tab switch preserved all 4 turns, History showed both real auto-generated titles, reopening
      the older conversation loaded its own distinct turns/sources, delete removed it from the
      list live. Screenshots saved (`01-answer-in-focus.png` … `05-reopened-conversation.png`).
      Two PRE-EXISTING issues observed and explicitly NOT fixed (out of this pass's scope, see
      D42): an occasional stray tool-args JSON fragment appended to the answer text on some real
      turns, and a CSS specificity quirk where `.tl-summary`-style pill hovers can show the
      global button hover fill instead of their own.
- [x] Docs + decision logged in `DECISIONS.md` (D42); commit.

### T7 — Four surgical fixes: stray tool-JSON, citation format, CSS hover bug, dot-dir exclusion
**Trigger:** D42's two observed-but-not-fixed issues (stray tool-args JSON tail; the CSS hover
specificity bug), a citation-consistency tightening, and a real-corpus ingest finding
(`.session_memory/*.md` junk not pruned by the agent's directory walk).
**Files:** `adapters/llm/openai_compat.py`, `pipelines/answer.py`, `web/src/App.css`,
`web/src/{Chat,Search,Library}.tsx`, `agent/sync.py` (CROSS-BOUNDARY).

- [x] `_strip_trailing_tool_json()` (`adapters/llm/openai_compat.py`) — bracket-matched backward
      scan strips a trailing tool-call-args-shaped JSON fragment glued onto otherwise-prose
      `ToolCompletion.content`; a no-op unless the text ends with `}` AND has non-empty prose
      before the matching `{` (a reply that IS one whole JSON object is left untouched). Applied
      in `_complete_native`'s no-tool-calls return AND all three `parse_prompted_response`
      fallback returns. TDD: 5 new tests in `tests/surface/adapters/test_llm_tool_calling.py`
      (native plain-string tail, native content-block-list + tail combined, prompted plain tail,
      prompted nested-object tail, whole-reply-is-JSON guard) — all red before, green after.
- [x] Citation format tightened in `pipelines/answer.py._SYSTEM_PROMPT`: exact shape spelled out
      literally — `"(filename.ext, p.N)"`, always comma-separated, always parenthesized, placed
      after the sentence it supports, with a concrete before/after example naming the bug
      (`.../Morgan.pdf,1.` fused into a path). New
      `test_system_prompt_requires_parenthesized_comma_separated_citations` alongside the
      existing `test_system_prompt_steers_enumeration_to_list_documents_alone`.
- [x] CSS hover-specificity bug (`web/src/App.css`) — root cause: `button:hover:not(:disabled)`'s
      bare `button` type selector tipped its specificity above single-class component-local
      hover rules (`.tl-summary:hover`, `.copy-btn:hover`, etc.), silently overriding every
      ghost/pill button's own hover. Fixed by scoping the solid-fill hover to a new
      `.btn-primary` class, applied to Send (`Chat.tsx`), Search (`Search.tsx`), and the Library
      FAB (`Library.tsx` — its own hand-duplicated identical `background`/`:hover` deleted in
      favor of the shared class). No CSS test harness in this repo; verified via a headless-
      Chrome computed-style audit (see below) instead.
- [x] `agent/sync.py._is_excluded_dir` (CROSS-BOUNDARY) — any directory whose basename starts
      with `.` is now pruned unconditionally, on top of (never instead of) the fixed named/suffix
      checks — closes the `.session_memory/*.md` gap. New
      `test_collect_prunes_hidden_directories_by_default` (root + nested hidden dirs); existing
      named-exclude/normal-folder tests unchanged and still green.
- [x] Full suite 403/403 green (was 396; +7) in a 2G-capped scope; `ruff check`/
      `ruff format --check` clean; `pyright` unchanged in kind (same pre-existing
      `test_routes.py` errors as D38/D40/D42). `npm run build`/`npm run lint` clean (one
      pre-existing `SystemMenu.tsx` exhaustive-deps warning, confirmed present before this pass).
- [x] Live re-verify: fresh `sift-engine-wp2` restart; `POST /v1/answer` for "who would fit a
      creative XR project?" (D42's own named repro prompt) run 2/2 — zero `{`/`}` in either
      answer, citations rendered as `(path, p.N)`. Headless-Chrome hover audit
      (`playwright-core`, real Chrome) read `getComputedStyle(...).backgroundColor` before/
      during a real `:hover` on every button class app-wide: Send/Search/Library FAB correctly
      darken `#7c5cff`→`#6a45f0`; every other button (`.copy-btn`, `.tl-summary`/
      `.sources-summary`, `.chat-history-btn`, `.sys-chip`, `.drawer-close`, `.drawer-del` in
      both drawers, `.history-open`, inactive tabs) never shows that fill, each keeping its own
      local hover. Screenshot saved: `06-hover-fixed.png`.
- [x] Docs + decision logged in `DECISIONS.md` (D43); commit.

### T8 — Temporal knowledge in tool payloads: `modified_at`/`indexed_at` everywhere + honesty rule
**Trigger:** Quentin's live observation — asked "when were those documents written?", the chat
model answered from filename archaeology and then claimed it has no metadata access, even
though the store holds true file mtime per document (`files.modified_at`, D28) plus the chunk
metadata dict; the tool payloads simply never serialized the documents-listing shape's temporal
fields, and neither the tool descriptions nor the system prompt told the model these fields
exist.
**Files:** `core/types.py`, `adapters/store/{fake,libsql}.py` (CROSS-BOUNDARY on `libsql.py`),
`api/schemas.py`, `api/{routes,v1}.py`, `pipelines/tools.py`, `pipelines/answer.py`,
`web/src/Library.tsx`.

- [x] `core/types.py::DocumentInfo` gains additive `modified_at`/`indexed_at: str | None = None`
      (mirroring `Hit`'s own pair). Audited `Chunk`/`Hit`/`ToolSearchHit`/`ToolChunk` first —
      already carried `modified_at`+`metadata` end-to-end since D28/the metadata-channel
      decision; only `DocumentInfo` (the `list_documents`/`GET /documents`/`GET /v1/tools/
      documents` shape) had never grown the fields.
- [x] `adapters/store/fake.py::FakeVectorStore.list_documents` reads its existing per-tenant
      `_modified_at`/`_indexed_at` dicts (already populated at `upsert`); `adapters/store/
      libsql.py` (CROSS-BOUNDARY) — `_SELECT_DOCUMENTS_BASE`/`_list_documents_job` select
      `f.modified_at, f.indexed_at` (both already free columns on `files`, no new migration).
- [x] `api/schemas.py::DocumentSummary` (shared by `GET /documents` and `GET /v1/tools/
      documents`) gains the matching two additive fields; both routes pass them through.
      `get_document_chunks`/`search` payloads audited and found already correct — no code
      change, only new tests locking the behavior in against fake AND a real `tmp_path` libSQL
      DB (per the task's own ask).
- [x] `pipelines/tools.py` — all three tool descriptions now name which fields carry
      `modified_at`/`metadata` and say to answer time/recency questions from `modified_at`,
      never a filename-embedded date. `pipelines/answer.py._SYSTEM_PROMPT` gains a new
      paragraph: answer "when was this written" from `modified_at`, phrase it as "last
      modified `<date>`" (NOT authorship — a re-save/copy refreshes mtime), say "unknown"
      when `modified_at` is null.
- [x] **Found during live re-verify, not originally scoped:** the model guessed
      `list_documents(metadata={"source": "NothingAD"})` for "the NothingAD documents" — a tag
      never set at ingest — got zero results, and answered "no such documents" instead of
      falling back to an unfiltered listing (reproduced 2/2). Fixed with an explicit new
      strategy bullet: never invent a `metadata` filter from a name/folder in the question
      (it almost always lives in the file `path`) — call `list_documents` with NO filter and
      match by `path` yourself. A softer first wording did NOT change the model's behavior on
      retest; only a maximally explicit/directive version did.
- [x] `web/src/Library.tsx`'s `DocumentSummary` mirror type gains the two optional fields
      (additive, not yet rendered in the panel).
- [x] TDD throughout: `tests/contract/test_store_contract.py`/`test_libsql_store.py` (fake +
      real libSQL), `tests/pipelines/test_tools.py` (all three executors, fake + real
      `tmp_path` `LibSQLStore` through the actual registry — `_seed`'s annotation widened
      `FakeVectorStore` → the `VectorStore` port so pyright accepts both), description tests,
      `tests/pipelines/test_answer.py` (temporal-honesty prompt + metadata-filter-guessing
      warning), `tests/contract/test_schemas.py` (round-trip), `tests/surface/api/
      test_documents.py`/`test_v1_tools.py` (API-level round-trip). 426/426 full suite green
      (was 403; +23) in a 2G-capped scope; `ruff check`/`ruff format --check` clean; `pyright`
      unchanged in kind (44 errors, identical to the pre-existing baseline, confirmed by
      diffing before/after). `npm run build`/`npm run lint` clean (same pre-existing
      `SystemMenu.tsx` warning as D42/D43).
- [x] Live re-verify (real Mistral `mistral-small-latest`, fresh `sift-engine-wp2` restart on
      `:8001`): `GET /v1/tools/documents`/`GET /documents` both confirmed carrying real
      `modified_at`/`indexed_at`. `POST /v1/answer` for "When were the NothingAD documents
      last modified?" — first pass (before the metadata-filter fix) reproducibly wrong 2/2
      (guessed filter, answered "no such documents"); after the fix, 2/2 correct — cites the
      real `2026-06-17T17:50:07.974008+00:00` timestamp, phrases it as "last modified", never
      claims a lack of metadata access.
- [x] Docs + decision logged in `DECISIONS.md` (D44); commit.

### T9 — Agent path-keying consistency (CROSS-BOUNDARY) + truthful `skipped_dedup` counters + a watch-mode runbook
**Trigger:** a live self-test against the real Acme corpus (50 docs, ingested one-shot then
handed to `--watch`) found `agent/sync.py::collect_roots()` keyed every file by ABSOLUTE path
while one-shot `collect()` keyed root-relative — a `--watch` reconcile against that corpus never
matched anything and re-uploaded (almost) the whole tree every restart (masked as "correct" only
by the engine's own content-hash dedup); the `Summary.skipped` counter also never tallied that
server-side `skipped_dedup` result, so it misleadingly read `0 skipped` the whole time.
**Files:** `agent/sync.py` (CROSS-BOUNDARY, Arthur-owned), `tests/agent/test_sync.py`,
`scripts/run-agent-watch.sh` (new).

- [x] `collect_roots()` now keys root-relative POSIX for a single root — byte-for-byte identical
      to `collect()` — via a shared `_name_root()` helper. Failing test first:
      `test_collect_roots_single_root_matches_collect_keys`.
- [x] Multi-root case: each key prefixed with its root's basename (`_root_prefixes()`),
      deterministic `-2`/`-3`/… disambiguation on a basename collision across roots, in root
      order (never set/dict iteration order). Overlapping/nested roots still dedup by resolved
      physical path (unchanged behavior). Tests: `test_collect_roots_multi_root_prefixes_with_
      basename`, `test_collect_roots_disambiguates_basename_collisions_deterministically` (both
      root orders asserted).
- [x] The exact live repro turned into a permanent regression:
      `test_reconcile_against_one_shot_manifest_skips_all_client_side` +
      `test_sync_against_one_shot_manifest_uploads_nothing` — 50 one-shot-keyed hashes → 0
      uploads, 50 client-side skips, zero `POST /ingest` calls.
- [x] `delete_removed` interplay checked explicitly: the actual `DELETE` is keyed by content hash
      (server-side), unaffected by the local key-scheme change — verified, not just assumed, by
      two new end-to-end regressions (single-root and multi-root/prefixed) that create a file,
      sync, delete it from disk, re-sync with `delete_removed=True`, and assert the `DELETE`
      targets the correct hash.
- [x] `sync()` now tallies a server-side `skipped_dedup` ingest result into `Summary.skipped`
      (`skipped=len(actions.skip) + skipped_dedup`), including inside a `PartialIngestError`'s
      merged partial response. Tests: `test_sync_tallies_server_side_skipped_dedup_into_summary`,
      `test_sync_tallies_skipped_dedup_within_partial_batch_failure`.
- [x] Migration note (no code): confirmed live via `GET /documents` on the real 50-doc corpus —
      zero absolute-style paths present; the only document that would have had one (this
      session's own transient self-test file, ingested via `--watch` before this fix) was already
      deleted. No backfill needed.
- [x] `scripts/run-agent-watch.sh` (new, executable): mirrors `run-engine.sh`'s cgroup posture
      (`MemoryMax`/`MemorySwapMax=0`/no `MemoryHigh`/`OOMPolicy=kill`/`Restart=always`/
      `RestartSec=3`) plus `--setenv=PYTHONUNBUFFERED=1` (stdout is block-buffered once redirected
      to a file — without this the log lagged minutes behind real activity). Parameterized
      (`WATCH_DIR`, `SERVER`, `SIFT_TOKEN` required, `AGENT_MEM_MAX` default `1G`, `LOG_FILE`
      default `~/.local/state/condense/agent-watch.log`).
- [x] Every pre-existing `collect_roots()`/`sync()` test keyed on the old absolute-path scheme
      updated to the new relative/prefixed keys (same behavior class, corrected expectation, none
      deleted). 435/435 full suite green (was 426; +9) in a 2G-capped scope; `ruff check`/
      `ruff format --check` clean.
- [x] Docs + decision logged in `DECISIONS.md` (D45); commit + push.
- [ ] Live restart of `sift-agent-watch` (worktree code) + verify against the real engine
      (`GET /documents` still exactly 50; first post-restart `[sync]` line shows ~50 skipped/0
      indexed/0 deleted; no bulk re-upload burst in the engine journal) — reported directly, not
      re-committed (this doc's own record stays test-based; see channel/task report for the live
      result).

### T10 — Grounding modes: the corpus-vs-general-knowledge trust boundary (Chat toggle)
**Trigger:** Quentin's live use of Chat surfaced that `/v1/answer` would silently free-generate
from the model's own training knowledge when a user said "ignore the database" — an answer that
rendered in the exact same card as a real, cited one (no citations either way), with no way for
a reader to tell them apart.
**Files:** `config.py` (`answer_grounding_default`), `api/schemas.py` (`AnswerRequest.grounding`,
`AnswerResponse.grounding_used`/`from_general_knowledge`), `pipelines/answer.py` (per-mode system
prompt suffixes + the `grounding` event/flag), `api/v1.py` (threading + response assembly),
`.env.example`/`docker-compose.yml` (env parity), `web/src/Chat.tsx`/`App.css` (Strict/Hybrid/
Open toggle + a "from general knowledge" chip — coordinated with the parallel rich-markdown
work, which owns the message body's rendering; this pass touched only the header control, the
per-message chip, and the fetch body).

- [x] `Settings.answer_grounding_default: Literal["strict","hybrid","open"] = "strict"`;
      `AnswerRequest.grounding` optional per-request override (`None` falls back to the
      setting). Failing tests first: defaults, `hybrid`/`open` accepted, a bogus value 422s/
      raises `ValidationError` at both the `Settings` and API layers.
- [x] `pipelines/answer.py`: a `_GROUNDING_STRICT_SUFFIX`/`_GROUNDING_HYBRID_SUFFIX`/
      `_GROUNDING_OPEN_SUFFIX` appended to `_SYSTEM_PROMPT` per the resolved mode — strict names
      the exact "ignore the database" jailbreak shape and instructs an explicit refusal; hybrid/
      open instruct a literal `"[General knowledge]"` marker on any ungrounded content.
      `from_general_knowledge` is computed from that marker in hybrid/open, but hardcoded
      `False` in strict regardless of the model's actual output — a structural guarantee over
      what the *response claims*, independent of whether the model obeyed the prompt. A new
      `"grounding"` `AnswerEvent`/SSE frame (`grounding_used`, `from_general_knowledge`) is
      emitted right before `"done"`, every mode, every turn; `AnswerResponse` gains the same two
      fields as top-level convenience fields (mirroring how `sources` already works, D42).
- [x] TDD: `tests/pipelines/test_answer.py` (11 new — default-to-settings, per-request override,
      each mode's suffix present, the strict jailbreak-refusal test, the "model misbehaves
      anyway" structural-guarantee test, hybrid/open marker-present/absent flagging, event
      ordering), `tests/surface/api/test_v1_answer.py` (existing trace/SSE ordering assertions
      extended for the new event, default/override/bogus-value at the HTTP layer),
      `tests/surface/test_config.py`, `tests/contract/test_schemas.py` (round-trips).
      `.env.example`/`docker-compose.yml` gain `ANSWER_GROUNDING_DEFAULT` — the standing
      `tests/contract/test_config_env_parity.py` caught the initial omission (red, then green).
- [x] `web/src/Chat.tsx`: a `GroundingSelector` (Strict/Hybrid/Open, a compact segmented pill
      mirroring the Search/Chat tab bar's `.tabs`/`.tab-btn` language) in the chat header,
      persisted to `localStorage` and threaded into every `POST /v1/answer` body; the new
      `grounding` SSE event is handled and stored per-turn; a message with
      `fromGeneralKnowledge` renders a subtle `.gk-chip` ("from general knowledge — not your
      documents"). New CSS added beside (not instead of) the existing header-control rules.
- [x] Full backend suite green (453/453, was 435; +18) in a 2G-capped scope; `ruff check`/
      `ruff format --check` and `pyright` (touched files) both clean. `npm run lint` clean.
      `npm run build` **not** clean at time of landing — blocked by an unrelated, still-in-flight
      typing gap in the parallel rich-markdown work (`web/src/markdown/prism.ts`, missing
      `prismjs` type declarations); confirmed by isolating the `tsc` error list, zero errors
      trace to any file this task touched (`Chat.tsx`/`App.css`).
- [x] Docs + decision logged in `DECISIONS.md` (D46); commit + push.
- [x] Live verify against `sift-engine-wp2`/`sift-web-wp2` (real Mistral): the Chat toggle driving
      hybrid mode end to end against the real model — done as part of T12 (D48) below, which
      found and fixed two live bugs in exactly this flow (SSE stall + no visible marking). The
      "ignore the database" strict-mode jailbreak itself remains unexercised live (T10's original
      scope) — deferred, no live bug reported against it.

### T11 — Rich markdown chat rendering: real tables, highlighted code, lazy Mermaid, no horizontal drag
**Trigger:** Quentin's screenshot of a `docker-compose.yml` answer — a GFM table rendered as raw
pipe text (no `remark-gfm`), and an unstyled fenced code block with no `overflow-x` dragged the
WHOLE chat column sideways.
**Files:** `web/package.json` (+`remark-gfm`, `prism-react-renderer`, `mermaid`), new
`web/src/markdown/{ChatMarkdown,CodeBlock,MermaidBlock,prismBash}.tsx|ts`, `web/src/Chat.tsx`
(message-body rendering only — coordinated with the parallel grounding-modes work, which owns
the header/toggle/chip in the same file), `web/src/App.css`.

- [x] `ChatMarkdown` (new): `react-markdown` + `remark-gfm`, custom `pre`/`table` renderers.
      `pre` is overridden alone (never `code`) — per the markdown spec a `<pre>` wraps ONLY a
      fenced/indented code block, inline code never gets one, so this cleanly separates the two
      cases with no fragile inline-vs-block heuristic. A ```` ```mermaid ```` fence routes to
      `MermaidBlock`; every other fence routes to `CodeBlock`. No `rehype-raw` — model-emitted
      HTML renders as inert escaped text, never live markup (sanitization requirement).
- [x] `CodeBlock` (new): language label (from the fence info string) + a copy button (reused
      `.copy-btn`/"Copied ✓" pattern from `Search.tsx`'s machine-mode copy) + `prism-react-
      renderer` syntax highlighting, in its OWN `overflow-x: auto` box with `max-width: 100%` —
      this is the actual fix for the reported drag bug. An unrecognized/absent language falls
      back to unhighlighted "text" rather than crashing `Highlight` on a missing grammar.
      `prismBash.ts`: `prism-react-renderer`'s bundled language set covers yaml/json/python/
      typescript/tsx/sql out of the box but not bash/shell — registered a small hand-written
      grammar (comments/strings/`$VARS`/keywords/builtins/flags) directly onto the vendored
      `Prism` singleton rather than pulling in a second highlighter or the full `prismjs`
      package for one language (see the D47 decision below on why that costs MORE, not less).
- [x] `MermaidBlock` (new): `import('mermaid')` only inside a `useEffect`, only when a
      ```` ```mermaid ```` fence is actually encountered — confirmed via production build output
      that `mermaid`'s entire dependency graph (mermaid.core/parser/per-diagram-type chunks,
      plus its own heavy lazy deps like cytoscape/katex) are separate chunks NEVER referenced by
      `dist/index.html`, i.e. zero bytes on initial page load regardless of how many chat
      messages exist, as long as none contain a mermaid fence. Renders the diagram's own SVG
      (`securityLevel: 'strict'`, mermaid's own label-sanitizing mode); on a parse error, falls
      back to `CodeBlock` showing the raw fence rather than a broken diagram or a crash.
- [x] Table rendering: `table` wrapped in `.md-table-wrap` (its own `overflow-x: auto`) — a wide
      table scrolls within itself, never the chat column.
- [x] **The no-horizontal-scroll rule, made structural, not just per-component:** `.chat-thread`
      gets a hard `overflow-x: hidden` backstop; `.chat-turn`/`.chat-assistant`/`.chat-answer`/
      `.recap` get `min-width: 0` (the flexbox default-`min-width:auto` trap that lets a wide
      descendant stretch its flex-item ancestor instead of scrolling within itself); `.recap`
      gets `overflow-wrap: anywhere` as a safety net for a long unbroken prose URL/token outside
      any code block.
- [x] **Two real rendering bugs found and fixed during live verification (not caught by
      `npm run build`/`lint` — both were runtime-only, CSS-cascade bugs):**
      1. `.recap`'s new `overflow-wrap: anywhere` inherits into `.code-block-pre` — and Chrome
         honors `overflow-wrap: anywhere` even under `white-space: pre`, silently defeating the
         "code never wraps, only scrolls" contract. Fixed with an explicit `overflow-wrap:
         normal` on `.code-block-pre` (and on `.md-table-wrap`'s `nowrap` cells, same interaction).
      2. **The one that actually produced "every code token on its own line":** this app already
         has an unrelated `.token { display: flex; ... }` class (the bearer-token input row in
         the header) — `prism-react-renderer` names every highlighted span's base class
         literally `"token"` (e.g. `class="token keyword"`), so EVERY syntax-highlighted span in
         every code block was inheriting `display: flex` from a class that has nothing to do
         with syntax highlighting. A flex-formatted span is a block-level box, so each token
         started its own visual row. Fixed by scoping `.code-block-pre .token { display: inline;
         }` — the header's own `.token` rule is untouched everywhere else. Found via a headless-
         Chrome computed-style/DOM inspection (`getComputedStyle(span).display === 'flex'`), not
         visible from the HTML structure alone (which was already correct).
- [x] **A bundle-size path NOT taken, worth recording:** first attempt at trimming
      `prism-react-renderer`'s ~40-language default bundle was a hand-built minimal Prism
      instance (`prismjs/components/prism-core` + `loadLanguages(['yaml',...])`) passed via
      `Highlight`'s `prism={...}` escape hatch. Measured result: the MAIN chunk grew from
      480.12 kB to 514.21 kB (gzip 147.91 kB → 159.46 kB) — WORSE, not better — because
      `Highlight`/`themes` still bundle prism-react-renderer's own vendored default Prism+
      languages regardless of whether the `prism` prop is used (confirmed: that vendored bundle
      lives in the same non-splittable module as `Highlight` itself). Reverted to the simple
      default bundle + the hand-written bash grammar (above) instead of paying for both.
- [x] `npm run build`/`npm run lint` clean (one pre-existing `SystemMenu.tsx` exhaustive-deps
      warning, same as D42-D46) — this ALSO resolves D46's implementation-log note that
      `npm run build` was blocked by an in-flight `prism.ts` typing gap in this task; that file
      no longer exists (reverted per the bundle-size finding above).
- [x] Live re-verify (`sift-web-wp2` `:5174`, real Vite hot-reload of the actual source — the
      backend's `/v1/answer` fetch was intercepted with a scripted SSE stream carrying a fixed
      test answer, same "canned model, real pipeline code" pattern as this WP's other harnesses,
      via a Playwright/`google-chrome` headless script since the `claude-in-chrome` MCP tools
      were unreachable this session): a GFM table (3 rows), a `docker-compose.yml` yaml fence (the
      exact repro shape), a python fence, and a `graph TD` mermaid fence all rendered correctly
      in one message — table as a real `<table>`, code highlighted with a working copy button
      (clipboard read back and asserted), mermaid as an actual SVG diagram (not the fallback
      code path) loaded via a genuinely separate `mermaid.js`/`mermaid.core`/`mermaid-parser.core`
      request, zero console errors, and `chat-thread.scrollWidth === chat-thread.clientWidth`
      (no horizontal overflow) throughout. Screenshots taken before/after both CSS fixes above,
      confirming the reported drag bug and the token-collision bug are both actually gone, not
      just theoretically fixed.
- [x] Bundle sizes (production build, gzip in parens) — main chunk: baseline (pre-WP-C)
      352.25 kB (107.50 kB) → +`remark-gfm` only 390.59 kB (119.64 kB) → + `prism-react-renderer`
      + `CodeBlock`/table components 481.47 kB (148.38 kB). **Net delta: +129.22 kB raw / +40.88
      kB gzip** (≈12.1 kB gzip for GFM tables, ≈28.3 kB gzip for the highlighter). CSS: 22.16 kB
      (5.09 kB) → 24.46 kB (5.42 kB), +0.33 kB gzip. **`mermaid`: +0 bytes on initial load** —
      `dist/index.html` references only the main JS+CSS; mermaid's own chunk graph
      (`mermaid.core` 35.08 kB/11.74 kB gzip + `mermaid-parser.core` 16.58 kB/3.92 kB gzip as the
      floor, plus further per-diagram-type chunks only pulled for the diagram kind actually used)
      loads solely via the runtime `import('mermaid')`.
- [x] Docs + decision logged in `DECISIONS.md` (D47); commit + push.

### T12 — Hardening: SSE stream finalization (BUG-1) + structured grounding segments (BUG-2)
**Trigger:** Quentin's live bug reports in the `:5174` hybrid-mode Chat UI. **BUG-1:** the repro
query ("Describe how Nothingad looks like other projects...") hung on "thinking..." forever —
the answer only appeared after a page refresh (server had persisted the turn; the SSE stream
never finalized in the UI). **BUG-2:** that same answer visibly mixed grounded facts with
unrelated general knowledge (Salesforce/HubSpot/etc.), but the UI showed no visible marking at
all beyond the subtle message-level chip. Plus an explicit ask to make the API stricter about
which content is grounded vs general knowledge — a structured distinction, not just an inline
marker + a boolean.
**Files:** `pipelines/answer.py` (loop/bookkeeping try/except hardening + `_split_grounding_
segments`), `api/schemas.py` (`GroundingSegment`, `AnswerResponse.grounding_segments`),
`api/v1.py` (`_sse_events` belt-and-suspenders + response assembly), `web/src/Chat.tsx`
(stream-close safety net + segment-by-segment rendering), `web/src/App.css` (`.gk-segment`).

- [x] **Root cause (BUG-1), found with evidence before fixing:** reproduced the exact query
      against a freshly-restarted `sift-engine-wp2` — 3/4 back-to-back `curl -N` streaming runs
      came back truncated (`curl` exit 18) instead of a clean SSE stream. Engine journal: the
      tool-calling loop only caught `TimeoutError` around the completer call; a genuine
      `httpx.HTTPStatusError: 429 Too Many Requests` from real Mistral propagated straight out of
      the async generator, uncaught, crashing `StreamingResponse` mid-flight AFTER headers were
      already flushed — no terminal `"done"` frame ever sent. `Chat.tsx` only cleared
      `streaming` inside the `"done"` branch, so a cut-short stream left the turn stuck forever.
      Hybrid's longer multi-hop answers make more completer round-trips, raising the odds of
      hitting exactly this window — explains "correlates with hybrid/longer answers." **Not
      hypothetical:** the identical 429 fired again live during THIS session's own re-verify
      (journal `02:28:43`) and the new code visibly caught it and finalized cleanly.
- [x] Server: `AnswerPipeline.run`'s tool-calling loop wrapped in an outer `try/except
      Exception` (not just `TimeoutError`) — ANY completer/tool failure now degrades to the SAME
      graceful `truncated=True` outcome the timeout path already had. Post-answer bookkeeping
      (persist, auto-title, JSON coercion, segment-splitting) wrapped the same way. `api/v1.py::
      _sse_events` adds an independent second line of defense: a `try/except/finally` that
      forces one synthetic `"done"` frame onto the wire if the pipeline's own generator somehow
      still didn't emit one.
- [x] Frontend: `Chat.tsx::send()` runs one more `patchAssistant` right after `readSse()`
      returns that force-finalizes the turn (`streaming: false`, `truncated: true`) ONLY if it's
      still marked `streaming` — a no-op on the normal `"done"` path, a safety net otherwise.
      Unrecognized SSE event types were already silently ignored (confirmed, documented inline).
- [x] `pipelines/answer.py::_split_grounding_segments(text, mode)` (BUG-2 + API strictness):
      splits the final answer into ordered `{"text", "kind": "grounded"|"general_knowledge"}`
      segments on marker BOUNDARIES (not line boundaries, so inline same-line mixing and
      one-marker-per-bullet-line both split correctly); `"strict"` is the same structural
      guarantee as `from_general_knowledge=False` (always one `"grounded"` segment).
      `from_general_knowledge` is now derived from `segments`, one source of truth. New
      `"grounding"` event field `segments`; new `api.schemas.GroundingSegment` +
      `AnswerResponse.grounding_segments`.
- [x] `Chat.tsx` renders `turn.groundingSegments` segment-by-segment (falls back to the old
      single-blob render when segments aren't available yet, same live-only convention as
      `groundingUsed`/`fromGeneralKnowledge`). A `general_knowledge` segment gets a `.gk-segment`
      wrapper: the app's existing purple accent tokens, a left border, tinted background, and a
      small "GENERAL KNOWLEDGE" tag. The message-level `.gk-chip` is unchanged (kept per
      Quentin's explicit ask).
- [x] TDD: `tests/pipelines/test_answer.py` (+9 — a completer that raises mid-loop, both on the
      first call and after a tool call already ran, still reaches `"grounding"`→`"done"`
      truncated; `_split_grounding_segments` across strict/hybrid/open, inline-mixed content,
      multi-bullet content, empty-answer edge case; every pre-existing exact-equality
      `grounding.data` assertion extended with `segments`, not weakened). `tests/surface/api/
      test_v1_answer.py` (+2 — an end-to-end HTTP SSE run where the completer raises mid-loop
      still reaches `"done"`/`truncated=True`; a hybrid SSE run's segments carry both kinds over
      the wire). `tests/contract/test_schemas.py`: `GroundingSegment` round-trips, rejects an
      unknown `kind`, `grounding_segments` defaults to `[]`.
- [x] 460/460 full suite green (was 453; +7 net), `ruff check`/`ruff format --check`/`pyright`
      (touched files) clean. `npm run build`/`npm run lint` clean.
- [x] Live verify (fresh `sift-engine-wp2` restart, real Mistral, real 50-doc Acme corpus,
      headless `google-chrome` via Playwright — `claude-in-chrome` MCP unreachable this session,
      same fallback as T5/T11): the exact repro query run 3× in hybrid mode — all 3 finalized
      cleanly (input re-enabled, "Send" restored, no stuck "Thinking…"), including one budget-
      truncated run and one run where the live 429 fired mid-loop and was still caught
      gracefully. Non-stream `POST /v1/answer` (`curl`, hybrid) confirmed `grounding_segments`
      present with correct kinds matching the real answer text. The purple marking itself
      confirmed via a scripted-SSE-response harness (same convention as T11's own verification —
      a fixed response intercepted via Playwright's `page.route`, driving the exact same
      `Chat.tsx` code), chosen over waiting on the live model's variable willingness to invoke
      the marker on any given run (independently confirmed structurally correct via the `curl`
      check above). Screenshots: `01-hybrid-completed.png` (real live Mistral run, clean
      finalization), `02-general-knowledge-marked.png` (purple segment + tag + message chip).
- [x] Docs + decision logged in `DECISIONS.md` (D48); commit + push.

### T13 — Parsing/chunking quality: xlsx "NaN" cell-filler cleanup + a degenerate-chunk floor (CROSS-BOUNDARY, Arthur-owned files)
**Trigger:** a read-only root-cause investigation across the Chat UI's "p. 1" badge, the
snippet-truncation mismatch between `pipelines/search.py`/`pipelines/tools.py`, and a real Acme
re-ingest surfaced two independent parsing/chunking quality bugs — both confirmed by actually
parsing the real motivating files, not guessed: (1) `MarkitdownParser`'s xlsx path renders every
empty/missing cell as the literal string `"NaN"` (pandas' `to_html(na_rep="NaN")` default) — a
real 82KB Acme budget spreadsheet came back with ~2,900 literal `"NaN"` occurrences, diluting
embeddings and making snippets unreadable; (2) `TokenChunker`'s fixed-token-count windows can
decode to a handful of real-but-useless characters (`"do. /"`, `"plantilla.)*"` observed live)
when a window's start lands on whitespace/template filler — genuinely what those tokens decode
to, but useless as a retrievable chunk, and it still got embedded and surfaced.
**Files:** `adapters/parsing/markitdown.py`, `adapters/chunking/token.py` (both Arthur-owned,
edited at Quentin's direction — flagged in `docs/channel/from-quentin.md`), `config.py`
(`chunk_min_chars`), `factory.py` (threading), `.env.example`/`docker-compose.yml` (parity),
plus both adapters' test files.

- [x] **xlsx NaN cleanup:** evaluated two approaches (see `DECISIONS.md` D50 for the full
      trade-off) — chose a narrow, xlsx-only post-parse cleanup (`_strip_xlsx_nan_fillers`) over
      a Condense-owned xlsx→text step that bypasses markitdown's `XlsxConverter` entirely, as the
      lower-risk option: it never touches markitdown's own conversion path (multi-sheet/merged-
      cell handling keeps working exactly as before), for a fix that's otherwise a one-parameter
      change (`to_html`'s `na_rep`) markitdown doesn't expose. Blanks a markdown-table CELL only
      when its ENTIRE trimmed content is exactly `"NaN"` — never a substring match, never a
      non-table line — applied right after conversion, before the existing `parse_max_chars`
      ceiling. The D34 used-range guard and D39 char-ceiling/timeout are both untouched. Failing
      tests first: a crafted xlsx fixture (empty cells beside real values) asserted zero `"NaN"`
      in the output with real values (`"alpha"`, `"beta-note"`) surviving.
- [x] Regression coverage for the two false-positive shapes the acceptance criteria named: a
      cell whose real content merely CONTAINS "NaN" (`"NaNoTech Corp"`) survives untouched; a
      `.txt` whose real prose contains the word "NaN" (a sensor-fault description) is untouched
      by the cleanup (xlsx-scoped only, not a general-purpose "NaN" scrubber). A pre-existing
      normal-small-xlsx regression test (`test_xlsx_within_threshold_still_parses`) still passes
      unchanged.
- [x] **Acceptance evidence — the two real motivating files, parsed directly (no live-DB
      writes):** `acme-budget_Annex-II_Rev.0(1).xlsx` and `...Rev.03.xlsx`
      (`/home/quentinlatimier/Documents/Acme/ACME-TOOLING/`) both now parse with **zero**
      `"NaN"` occurrences anywhere in the extracted text (was 2,904 / 2,994 respectively before
      the fix — measured directly, not estimated), while real content (`"PERSONAL"`, `"BUDGET"`
      sheet headers, etc.) is confirmed still present. Verification script kept in the session's
      scratchpad (not committed — no repo path references a corpus outside this repository).
- [x] **Degenerate-chunk floor:** `TokenChunker` gains `chunk_min_chars: int = 24`
      (config-driven via `Settings.chunk_min_chars`, `Field(ge=1)`, threaded through
      `factory.py::_build_ingest`'s `TokenChunker(...)`, `.env.example`/`docker-compose.yml`
      parity — the standing `tests/contract/test_config_env_parity.py` catches any future gap
      mechanically). A window is DROPPED (never merged into a neighbor — simpler, and
      `chunk_overlap` already means an adjacent window carries most of the same boundary text)
      when its decoded, whitespace-collapsed text is shorter than the floor; the emitted
      `Chunk.text` itself is unchanged (plain decode+strip — collapsing is only used to MEASURE
      length). `index` stays a document-global 0-based ordinal over exactly the emitted chunks
      (the pre-existing empty-window skip already worked this way) — verified against the
      store's actual schema: `LibSQLStore`'s `chunks` table is `PRIMARY KEY (tenant,
      source_hash, idx)`, which only needs uniqueness + a stable `ORDER BY idx ASC` (used by
      `get_chunks`), never assumes indices map 1:1 to token-window positions; version-collapse
      (D27) operates on retrieved `Hit` text similarity, unaffected by which chunks exist.
- [x] Failing tests first, using a new test-only `_WordTokenizer` (full deterministic control
      over window boundaries — real BPE ids don't map predictably enough to characters to
      engineer a specific short trailing window): reproduces the exact `"do. /"` shape and
      asserts it's dropped while emitted indices stay contiguous `0..n-1`; `chunk_min_chars < 1`
      raises `ValueError` (mirrors the existing `chunk_overlap >= chunk_size` guard); the
      existing long-text reference test's chunks are all `>= chunk_min_chars` under the real
      tiktoken tokenizer (confirms the default floor never fires on ordinary prose); the unwired
      constructor default (24) is asserted to match `Settings.chunk_min_chars`'s default.
- [x] **Re-ingest dependency, called out explicitly (both fixes):** `IngestPipeline.ingest`
      dedups by exact content-hash BEFORE parsing/chunking runs, so neither fix retroactively
      cleans an already-indexed, byte-unchanged document — an explicit delete + fresh re-ingest
      is required to pick up either improvement on existing docs. See `DECISIONS.md` D50 for the
      full reasoning (incl. why this makes the store-level "fewer chunks under the same hash"
      case a non-issue in practice: `delete_document` clears the old `idx` range first).
- [x] 467/467 full suite green (was 460; +7), `ruff check`/`ruff format --check`/`pyright`
      (touched files) clean.
- [x] Docs + decision logged in `DECISIONS.md` (D50); `docs/channel/from-quentin.md` update
      (CROSS-BOUNDARY on both Arthur-owned files); commit + push.

### T14 — Source-card UI quality: page-badge noise, snippet unification, query-term highlight
**Trigger:** the same read-only root-cause investigation behind T13 also named two Dev-B-owned
UI issues: (1) every source card shows a "p. 1" badge, but no parser today emits `page > 1` for
any format — it's pure noise; (2) `/search`'s snippet is whitespace-collapsed + truncated
server-side (`pipelines/search.py::_snippet()`), but the chat/toolbox path
(`pipelines/answer.py::_merge_sources`) sends a raw `text[:200]` — so the same citation reads
raggedly-wrapped in Chat but cleanly in Search. Quentin also asked for a third, purely cosmetic
addition: bold the query terms a snippet actually matches.
**Files:** `web/src/sourceSnippet.tsx` (new, shared), `web/src/Chat.tsx`, `web/src/Search.tsx`,
`web/src/App.css`. No backend files touched — see the snippet-unification decision below.

- [x] `showPageBadge(page): boolean` (`page > 1`) — one predicate, used identically by
      `Search.tsx`'s single source card and `Chat.tsx`'s `SourcesPanel`; self-activates the day a
      paginated parser actually emits `page > 1`, no further UI change needed then.
- [x] **Snippet unification — chosen approach:** normalize on the FRONTEND
      (`collapseWhitespace()`, `/\s+/g` → single space + trim) rather than touching
      `pipelines/answer.py::_merge_sources` — that file sits in `pipelines/` (co-owned) and the
      parsing/chunking agent (T13) was actively working nearby in the same work package;
      frontend-side normalization gets the identical visual outcome with zero collision risk and
      is provably idempotent (re-collapsing `/search`'s already-collapsed snippet is a no-op, so
      both source-card renderers can unconditionally apply it). Revisit unifying server-side
      later if `_merge_sources`'s truncation itself (200 vs `source_snippet_chars`'s 300) is ever
      judged worth aligning too — out of scope for this pass (cosmetic display, not a data
      contract change).
- [x] `highlightQueryTerms(text, query)` — bolds literal, case-insensitive, whole-word-ish
      (unicode-aware lookaround boundaries, not `\b`, so accented text in the many Spanish
      documents in the corpus boundary-matches correctly too) matches of `query`'s significant
      terms (stopwords + <3-char tokens dropped) inside a snippet. Returns React nodes built via
      `text.split(regex)`, never `dangerouslySetInnerHTML` — a `<mark>` child is exactly as safe
      as a plain-text child, so this can't become a markup-injection vector regardless of what a
      document's own content contains. `Chat.tsx` threads each assistant turn's own question
      through as `query` (new `AssistantTurn.question` field, set at turn-creation time and
      reconstructed from the preceding user turn when rehydrating persisted history) rather than
      some single page-level "current query" — each turn's sources highlight against the
      question THEY actually answer. `Search.tsx` captures the exact searched text into its own
      `queriedText` state (separate from the live `query` input) so editing the search box after
      running a search can't desync the highlight from what was actually searched.
- [x] `.snippet-hit` — the app's own existing purple accent tokens (`--accent-bg`/
      `--accent-strong`), not a generic yellow `<mark>` — reads as "this app noticed it," not a
      browser find-in-page.
- [x] `npm run build`/`npm run lint` clean.
- [x] Live verification interrupted mid-pass by a severe, sustained host-wide OOM-kill storm (see
      the implementation log entry below for the full account) — while paused, verified by
      exercising the REAL `tsc`-compiled `sourceSnippet.tsx` (not a reimplementation) against REAL
      source records fetched from the live `sift-engine-wp2` (a persisted NothingAD conversation),
      rendered through `react-dom/server`. The storm eased within the session; a real
      headless-Chrome pass (Playwright, `claude-in-chrome` MCP unreachable this session) then
      completed cleanly against the live `sift-web-wp2`/`sift-engine-wp2`: a real Chat turn (same
      persisted conversation) shows 3 sources, zero page badges, single-line collapsed snippets,
      "NothingAD" bolded in the app's purple accent; a fresh real `/search` call shows the same
      badge/whitespace behavior, with zero (correctly-declined) highlight hits on that particular
      passage since its actual text doesn't contain any significant query term as a whole word.
      Screenshots: `01-no-page-badge.png`/`02-snippet-clean.png` (Chat)/`03-highlight.png` (Search).
- [x] Docs + decision logged in `DECISIONS.md` (D49); commit + push.

### T15 — BUG-A/BUG-B: strict mode's OUTPUT is corpus-only (not just the flag) + per-turn grounding is persisted (not live-only)
**Trigger:** Quentin's live bug reports, one conversation, real Mistral. **BUG-A:** with the
header pill on STRICT, asking "And what are Bettair's competitors?" returned a full
general-knowledge answer literally prefixed `"[General knowledge]"`; strict must abstain, never
emit general knowledge. **BUG-B:** switching the pill mid-conversation made the purple
general-knowledge marking DISAPPEAR from a PREVIOUS message that had legitimately earned it.
**Files:** `pipelines/answer.py`, `core/types.py`, `adapters/conversation/{fake,libsql}.py`,
`api/{schemas,v1}.py`, `web/src/Chat.tsx`.

- [x] **Root cause (BUG-A), found with evidence, not the suspected cause:** the task's prime
      suspect was a stale-frontend-mode bug (`Chat.tsx` sending an earlier turn's grounding
      instead of the currently-selected pill). **Disproved**: a Playwright-driven repro against
      the real `:5174`/`:8001` captured the actual outgoing request body both for a hybrid turn
      (`"grounding":"hybrid"`) and the strict turn right after clicking the pill
      (`"grounding":"strict"`) — correct both times, before any code change. `send()` already
      reads `grounding` fresh at call time; no frontend fix was needed or made. The REAL cause:
      even with `grounding="strict"` genuinely in effect, the completer (real Mistral, hybrid-mode
      turns still in its history) emitted the hybrid/open `"[General knowledge]"` marker anyway
      and free-generated a real competitor list — the pre-existing guarantee (D48) only covered
      the *flag* (`from_general_knowledge` hardcoded `False`), never the answer *text* itself.
- [x] Strict structural OUTPUT guard (`pipelines/answer.py`): if `mode == "strict"` and the
      literal `"[general knowledge]"` marker (case-insensitive) appears anywhere in the raw
      answer, the WHOLE answer is replaced with a fixed abstention (`_STRICT_ABSTENTION_TEXT`)
      before it is ever segmented, persisted, or streamed — never just hidden behind the flag
      while the leaked prose stays on screen. `grounding_used`/`from_general_knowledge`/single-
      `"grounded"`-segment guarantees are unchanged.
- [x] **Root cause (BUG-B), found with evidence:** a plain pill click mid-session does NOT touch
      prior turns' React state (confirmed: the marking survived a live Strict click, both before
      and after this fix — `AssistantTurn`'s grounding fields were already immutable per-turn IN
      MEMORY). The actual trigger, reproduced live: ANY remount of `<Chat>` (tab switch away/back,
      History reopen, page reload) refetches the conversation, and because
      `ConversationStore.append_turn` never persisted grounding fields at all (D48's own deferred
      alternative (d)), `turnsFromDetail` unconditionally reset every historical turn's marking to
      "unknown" — discarding it even though the turn's raw text still held the (now unstyled)
      marker. Reproduced with a scripted Playwright pass: purple present after a hybrid answer →
      still present after switching to Strict in-session → **gone** after a Search-tab-then-back
      remount.
- [x] Per-turn immutable grounding persistence: `ConversationTurn` gains `grounding_used`/
      `from_general_knowledge`/`grounding_segments`; `ConversationStore.append_turn` gains the same
      three keyword params (assistant-turn-only, same shape as the existing `sources` param); both
      `FakeConversationStore`/`LibSQLConversationStore` persist them (three new ALTER-if-missing
      columns on the latter, same migration pattern as `sources`, verified against a legacy
      pre-`sources` table too). `AnswerPipeline.run` passes these into the SAME `append_turn` call
      that already persists the answer text — the BUG-A abstention is what actually gets stored,
      never the leaked content. `ConversationTurnOut`/`GET /v1/conversations/{id}` surface all
      three (`_known_grounding_mode` narrows the loosely-typed persisted value into the API's
      `Literal`, defensively mapping anything unrecognized to `None`). `Chat.tsx`'s
      `turnsFromDetail` now reads these from each turn's own persisted data instead of nulling
      them out on every reload.
- [x] Basis: TDD throughout, no live LLM in the automated suite. 475/475 full suite green (was
      467; +8), `ruff check`/`pyright` (touched files) clean. `npm run build`/`npm run lint` clean.
- [x] **Live verification** (fresh `sift-engine-wp2` restart, real Mistral, `:5174`/`:8001`,
      captured request bodies before AND after): hybrid turn → purple marking appears
      (`01-hybrid-purple.png`); switching to Strict → the prior message KEEPS its purple marking,
      both in-session and after a full tab-switch remount (`02-switched-strict-purple-persists.png`,
      `02b-purple-persists-after-remount.png`); a fresh general-knowledge question in Strict, run
      twice — captured request body both times shows `"grounding":"strict"` genuinely sent; run 1
      shows the model attempt to leak and the pipeline replace it with the abstention, run 2 shows
      the model itself abstaining honestly — neither run's page text contains the literal
      `"[general knowledge]"` marker or a leaked company list (`03-strict-abstains.png`).
- [x] Docs + decision logged in `DECISIONS.md` (D51); commit + push.

## 5. Test strategy

- **Unit/pipeline:** `FakeEmbedder`/`FakeVectorStore`/`NullReranker`/`FakeConversationStore` +
  a new `FakeToolCompleter` (scripted, deterministic responses) — **no live LLM calls
  anywhere in the automated suite** (hard rule). Real-model behavior is validated only in the
  E2E acceptance pass, run manually/scripted against the actual configured `Completer`, never
  as part of `pytest`.
- **API:** `TestClient` + `dependency_overrides`, exactly like the existing route tests;
  SSE responses read via `TestClient`'s streaming support.
- **Boundary/vocabulary enforcement:** the §3 tests are part of the standing regression suite
  from T3 onward, not a one-time check.
- **All suite runs:** `systemd-run --user --scope --same-dir -p MemoryMax=2G -p
  MemorySwapMax=0` (no `MemoryHigh`, no `OOMScoreAdjust` on a bare `--scope` — D34's
  standing policy).

## 6. Implementation log

| Date | Commit | Change |
|------|--------|--------|
| 2026-07-04 | (pending) | WP scaffolding: worktree, machine/human docs, channel announcement. Baseline 196/196 green on `origin/main` @ 197a836. |
| 2026-07-04 | (pending) | T1 foundations: additive `metadata` on `Chunk`/`Hit`/`Source`, threaded through `IngestPipeline`/`FakeVectorStore`/`LibSQLStore` (incl. ALTER-if-missing migration) and surfaced by `SearchPipeline`; new `api/v1.py` + `POST /v1/documents` JSON ingest. Metadata-equality/`since`/`until` filter seam **not** landed this pass (deferred, D37). 209/209 tests green (was 196; +13), ruff clean. See D37. |
| 2026-07-04 | (pending) | T2 toolbox: new `pipelines/tools.py` (`ToolRegistry`/`ToolSpec`, `search`/`list_documents`/`get_document_chunks`, both schema renders); the deferred filter seam landed as an additive `VectorStore.search(..., filters=)` + `SearchFilters` (`core/types.py`) plus `SupportsDocumentAdmin.list_documents(..., metadata=)` and a new `SupportsChunkAccess.get_chunks` — implemented in both `FakeVectorStore` and `LibSQLStore` (SQL `json_extract`/range/`EXISTS`, **CROSS-BOUNDARY** on the libSQL file). New `/v1/tools/{search,documents,documents/{hash}/chunks,schema}` routes, all bearer-authed, rendering only from the registry. `Settings.auth_tokens`/`tools_search_k`/`tools_search_max_k` added; `resolve_tenant` accepts any per-consumer token or the legacy `ingest_token`, logs the consumer name. Standing regression tests added: `PATCH /settings` structurally absent from the registry/schema, and the deferred vocabulary-rule grep (D37) with an explicit RAM/systems allowlist. 283/283 tests green (was 209; +74), ruff clean, pyright unchanged (pre-existing noise only, see D38). See D38. |
| 2026-07-04 | `c21819b`/`dbc1e77`/`6c9097a` | T4 guardrails: generic post-parse `parse_max_chars`/`parse_timeout_s` guards (`MarkitdownParser`), agent `DEFAULT_EXCLUDE_FILES` (**CROSS-BOUNDARY** on `agent/`) + engine `Restart=on-failure`, compose `sift-data` volume + `/healthz` healthcheck + `mem_limit`. 223/223 tests green (was 209; +14) at landing time. **Docs gap noted and backfilled while landing T3:** these three commits shipped without their `DECISIONS.md` entry in the same commit (CLAUDE.md §6) — see **D39** (written retroactively) and this doc's own T4 checklist (now ticked to match the real commits). |
| 2026-07-04 | (pending) | T3 `/v1/answer`: additive `ToolCompleter` port (`core/ports.py`) + `ToolCall`/`ToolCompletion` (`core/types.py`) — `messages`/`tools`-only signature, system folded into `messages[0]` (deviates from this doc's sketch, D40). `OpenAICompatCompleter.complete_with_tools` implements native OpenAI-style function-calling, a prompted strict-JSON ReAct fallback (with transcript-flattening for backends with no tool-calling awareness), and `Settings.answer_tool_mode="auto"`'s sticky native→prompted fallback; `answer_max_tokens` is its own budget, never aliasing `recap_max_tokens`. New `pipelines/answer.py` (`AnswerPipeline`, `AnswerEvent`, `ConversationStore` Protocol) drives the loop through `ToolRegistry.call(...)` exclusively — boundary rule enforced by `tests/pipelines/test_answer_boundary.py`, written first per the plan. Hard budgets (`answer_max_tool_calls`, `answer_timeout_s`) degrade gracefully (`truncated=true` + best-effort answer), never a raw error/hang. Conversation state: `FakeConversationStore` + a real `LibSQLConversationStore` (own connection, same async-over-sync shape as `LibSQLStore`) — a turn-numbering bug caught by TDD (`COUNT(*)` colliding with a surviving row's PK after the first ring-buffer trim) fixed via `MAX(turn) + 1` before landing. `POST /v1/answer` (non-stream + SSE) shares one event vocabulary (`AnswerEvent.to_dict()`) between both response modes. Drive-by: `.env.example`/`docker-compose.yml` env-parity gaps from T2/T4 (`TOOLS_SEARCH_K`/`MAX_K`/`AUTH_TOKENS`/`PARSE_MAX_CHARS`/`PARSE_TIMEOUT_S`) closed alongside this pass's own `ANSWER_*` keys. 332/332 tests green (was 223 per D39; +109), ruff clean, pyright unchanged in kind (D38-style scaling only). See D40. |
| 2026-07-04 | (pending) | T5 UI: `Chat.tsx` (new) — thread + `POST /v1/answer` `stream:true` SSE reader, per-turn activity timeline (one line per `tool_call`/`tool_result` pair, pulse while active, chevron-expand JSON detail, auto-collapses to a summary line once the turn finishes), final answer in the existing recap/source card style with citations pulled from `search` results seen along the way. `App.tsx` gains a Search/Chat tab bar (persisted to `localStorage`). `SystemMenu.tsx`: settings regrouped to mirror `.env.example`'s sections with a one-line hover explanation per key (reusing the existing mode-info tooltip), the `SettingsPatch` whitelist stays inline-editable with an optimistic "Saved ✓", model/URL/store/token keys greyed with a restart-hint badge. `vite.config.ts` gains the `/v1` proxy entry and an env-overridable `VITE_API_TARGET` (still defaults to `:8000`, no behavior change for normal dev). Verified visually via a locally-launched headless Chrome (the `claude-in-chrome` MCP tools were unreachable from this subagent session) against a dedicated dev instance (`sift-web-wp2`, `:5174`) driving a throwaway scratchpad harness that served the real FastAPI app with fakes + a scripted `ToolCompleter` (the production engine on `:8000` was down for unrelated reasons for this whole pass). `npm run build`/`lint` clean. |
| 2026-07-04 | `a6bba54`/`eca250b`/`5f4d401`/`c12741c`/`0ff8c65`/`da70fb0` | **Bugfix + hardening round, D40 amendment:** the first live-Mistral E2E pass (scenario (c)) found two reproducible bugs the automated suite's fakes can't catch by construction. **BUG #2:** Mistral's `message.content` can be a content-block LIST (`{"type":"text",...}`/`{"type":"reference",...}` interleaved) for a multi-cited answer, not a string — the raw list reached `LibSQLConversationStore` and crashed the DB bind, 500ing `/v1/answer`. Fixed with `_coerce_message_content()` (`adapters/llm/openai_compat.py`) so `ToolCompletion.content` is always `str`; conversation store now validates + raises a clear `TypeError` as defense-in-depth. **BUG #1:** `list_documents`/`get_document_chunks` executors (`pipelines/tools.py`) never called `ensure_ready()` like `search` does, so the first call against a not-yet-migrated libSQL DB 500'd (`no such column: c.metadata`) — reproduced against a real hand-built legacy-schema DB, fixed both in the executors AND (belt-and-braces) once at app-lifespan startup (`api/main.py`). Audit pass: `_call_tool` now catches ANY executor exception, not just `KeyError`; `answer_max_tool_calls` 6→10; full `Settings`↔`docker-compose.yml`/`.env.example` env parity (new permanent contract test, `tests/contract/test_config_env_parity.py`) closing a real gap (every `EMBED_*`/`OCR_*`/`RECAP_*`/etc. key was silently ignored by `docker compose up`); `parse_auth_tokens` redacts a malformed entry before logging (first 4 chars + length — a malformed entry could itself be a bare secret); `DocumentIngestRequest.text` ceiling now tied to `Settings.parse_max_chars` (422 on oversized). Re-verified against a fresh `sift-engine-wp2` process (real Mistral, real TEI, real `sift_local.db`): BUG #1 regression check (first-ever request = `GET /v1/tools/documents`) 200'd; BUG #2 regression check (scenario (c)) 200'd on 2/2 attempts with genuine multi-citation answers; scenario (a) rerun still `truncated: true` even at the new budget of 10 (the real corpus is 50 documents, not ~12-14 — reported honestly as NOT fixed, see `DECISIONS.md`'s D40 amendment for the full breakdown). 346/346 tests green (was 332; +14), `ruff check`/`ruff format --check` clean, `pyright` unchanged in kind (zero new errors from any file touched this pass). See D40 amendment. |
| 2026-07-04 | (pending) | **Enumeration-strategy fix, D41 (closes D40 amendment's last open item):** `pipelines/answer.py._SYSTEM_PROMPT` gained an explicit strategy section — tool-call budget is a handful of calls, plan before calling anything; `list_documents` ALONE is authoritative for "what documents/people/things exist" questions (its paths/counts don't need per-document verification); `get_document_chunks` is for a SMALL, already-identified set of documents, never for iterating the whole corpus; `search` is preferred for content questions. `pipelines/tools.py`'s three tool descriptions (the wire-level steering surface, rendered into `to_openai_functions()`) were extended with the same guidance in each tool's own words. No code-path/behavior change — pure prompt/description edit. TDD: `tests/pipelines/test_answer.py::test_system_prompt_steers_enumeration_to_list_documents_alone` (asserts the actual system message handed to the completer) + `tests/pipelines/test_tools.py::test_list_documents_description_says_authoritative_for_enumeration`/`test_get_document_chunks_description_warns_against_whole_corpus_iteration`, all red before the edit, green after. 349/349 full suite green (was 346; +3), `ruff check`/`ruff format --check` clean. **Live re-verify (real Mistral, real TEI, fresh `sift-engine-wp2` on `:8001`, same 50-doc Acme corpus):** scenario (a) rerun 3× — **all `truncated: false`, all 14 people/CVs enumerated every time** (run 1: one `list_documents` call, 2.53s; run 2: four `list_documents` calls — the model retried narrower metadata filters that came back empty before falling back to the full unfiltered list, 4.60s, never touched `get_document_chunks`; run 3: one `list_documents` call, 2.22s). Scenario (c) rerun once (`"who would fit a creative XR project?"`) — 200, `truncated: false`, one `search` call, four citations. See D41. |
| 2026-07-04 | (pending) | **T6 chat UX fixes (P1/P2), D42:** conversation metadata (`conversations_meta` table + additive `sources` column, both ALTER-if-missing) and a widened `ConversationStore` port (`set_title_if_unset`/`list_conversations`/`get_conversation`/`delete_conversation`) in both `FakeConversationStore`/`LibSQLConversationStore`; new `core/types.ConversationMeta`/`ConversationDetail`. Tool loop now emits a compact `sources` event/field (dedup+clamp+cap, server-side) persisted onto the assistant's own turn. Auto-title: one extra `Completer.complete()` call after the first answer (`title_completer`, reuses the recap's completer instance), `answer_autotitle_enabled` default `true`, graceful fallback to a truncated first message on any failure. New plain-REST `GET`/`DELETE /v1/conversations*` (deliberately NOT `ToolRegistry` tools — a standing regression test pins the registry to exactly 3 corpus tools). `Chat.tsx`: answer always renders before a collapsed sources pill and the activity pill (no full source wall by default), auto-scroll now respects a manual scroll-up (`pinnedToBottomRef` + `onScroll`); `conversation_id` persists to `localStorage` + refetches on mount (P2), new `ChatHistory.tsx` drawer (list/reopen/delete past conversations). 396/396 tests green (was 349; +47), ruff clean, pyright unchanged in kind. `npm run build`/`lint` clean. Live-verified against real Mistral (`sift-engine-wp2` restart, `sift-web-wp2`, headless Chrome): answer-in-focus + collapsed/expanded sources, no-scroll-trap follow-up, tab-switch persistence, History list/reopen/delete all confirmed working; screenshots saved. Two pre-existing issues observed and explicitly not fixed (out of scope): an occasional stray tool-args JSON fragment in some real answers, and a global CSS hover-specificity quirk on pill buttons. See D42. |
| 2026-07-04 | (pending) | **T7 four surgical fixes, D43:** `_strip_trailing_tool_json()` (`adapters/llm/openai_compat.py`) bracket-matches backward from a reply's end to scrub a stray tool-call-args JSON tail off `ToolCompletion.content` (both the native no-tool-calls path and all three `parse_prompted_response` fallback returns); a no-op when the reply IS one whole JSON object (nothing to scrub without erasing the answer). Citation format tightened in `pipelines/answer.py._SYSTEM_PROMPT`: literal `"(filename.ext, p.N)"` shape, always comma-separated + parenthesized, with a concrete before/after anti-fusing example. CSS hover-specificity bug fixed: the global solid-fill hover rule is now scoped to a new `.btn-primary` class (Send/Search/Library FAB) instead of bare `button`, so every ghost/pill button's own local `:hover` rule wins again (`.tl-summary`/`.sources-summary`, `.source-expand`, `.copy-btn`, `.chat-new`, `.chat-history-btn`, `.sys-chip`, `.drawer-close`, `.drawer-del`, `.history-open`) — Library FAB's own duplicated identical hover deleted in favor of the shared class. `agent/sync.py._is_excluded_dir` (CROSS-BOUNDARY) now prunes any dot-prefixed directory unconditionally, on top of the named/suffix set, closing a real `.session_memory/*.md` ingest gap. TDD: 5 new LLM-adapter tests, 1 new system-prompt citation test, 1 new agent hidden-dir test — all red before, green after; 403/403 full suite green (was 396; +7), ruff clean, pyright unchanged in kind, `npm run build`/`lint` clean. Live re-verify: fresh `sift-engine-wp2` restart, `POST /v1/answer` for D42's own named repro prompt 2/2 clean (no stray JSON, citations `(path, p.N)`); headless-Chrome computed-style hover audit across every button class in the app confirmed no ghost/pill button shows the global primary purple fill, and Send/Search/Library FAB correctly still do. Screenshot: `06-hover-fixed.png`. See D43. |
| 2026-07-04 | (pending) | **T8 temporal knowledge in tool payloads, D44:** `core/types.DocumentInfo` gains additive `modified_at`/`indexed_at` (both already-free columns on `files`, threaded through `FakeVectorStore`/`LibSQLStore` — **CROSS-BOUNDARY** on `libsql.py`), `api/schemas.DocumentSummary` + both `/documents`/`/v1/tools/documents` routes follow; `get_document_chunks`/`search` payloads audited and found already correct (D28). `pipelines/tools.py`'s three tool descriptions and `pipelines/answer.py._SYSTEM_PROMPT` now name `modified_at`/`metadata`, mandate answering time/recency questions from `modified_at` (never a filename date), and spell out the honest phrasing ("last modified `<date>`", not authorship; "unknown" when null). Found during live re-verify, not originally scoped: the model was guessing a `metadata` filter from a name in the question ("the NothingAD documents" → `metadata={"source": "NothingAD"}`, a tag that was never set) and giving up on the empty result — fixed with an explicit, maximally-directive prompt bullet (a softer first wording did not change the model's behavior). 426/426 full suite green (was 403; +23), ruff clean, pyright unchanged in kind (44 errors, confirmed identical to baseline by diffing). `npm run build`/`lint` clean. Live re-verify (real Mistral, fresh `sift-engine-wp2` restart): `/v1/tools/documents`/`/documents` both carry real `modified_at`; `POST /v1/answer` "When were the NothingAD documents last modified?" 2/2 correct after the fix — real timestamp, "last modified" phrasing, no metadata-access denial. See D44. |
| 2026-07-05 | (pending) | **T9 agent path-keying consistency + truthful counters + runbook, D45 (CROSS-BOUNDARY):** a live self-test against the real 50-doc Acme corpus found `agent/sync.py::collect_roots()` keying files by ABSOLUTE path while one-shot `collect()` keyed root-relative, so a `--watch` reconcile against a one-shot-ingested corpus matched nothing and re-uploaded almost the whole tree every restart (masked "correct" only by server-side content-hash dedup). Fixed: `collect_roots()` now matches `collect()` exactly for a single root (`_name_root()` shared helper); multiple roots get a basename prefix, deterministically disambiguated on collision (`_root_prefixes()`); overlap-dedup preserved by resolved physical path. `Summary.skipped` now also tallies a server-side `skipped_dedup` ingest result (previously silently dropped, including inside a `PartialIngestError`'s merged partial response). Two new end-to-end regressions verify `delete_removed` still deletes by the correct content hash under the new key scheme (single- and multi-root). Migration: confirmed live (`GET /documents`, 50/50 paths root-relative, zero absolute) that no backfill is needed — the one document that would've had an absolute-style path was already deleted. New `scripts/run-agent-watch.sh` (mirrors `run-engine.sh`'s cgroup posture + `PYTHONUNBUFFERED=1`). 435/435 full suite green (was 426; +9), `ruff check`/`ruff format --check` clean. See D45. |
| 2026-07-05 | (pending) | **T10 grounding modes, D46:** `/v1/answer` was silently free-generating from the model's own training knowledge when a user said "ignore the database", with no visible signal distinguishing that from a real, cited answer. Fixed with a first-class mode (`Settings.answer_grounding_default: Literal["strict","hybrid","open"]="strict"`, per-request `AnswerRequest.grounding` override): `strict` is corpus-only via `_GROUNDING_STRICT_SUFFIX` (names the exact jailbreak shape, instructs refusal, mandates honest abstention); `hybrid`/`open` may add general knowledge but must prefix it with a literal `"[General knowledge]"` marker. A new `"grounding"` `AnswerEvent`/SSE frame (`grounding_used`, `from_general_knowledge`) emits right before `"done"`; `AnswerResponse` surfaces the same two fields. `from_general_knowledge` is marker-detected in hybrid/open but hardcoded `False` in strict regardless of the model's actual output — a structural guarantee over the response, not a re-check of whether the model obeyed the prompt. `Chat.tsx` gained a `GroundingSelector` (Strict/Hybrid/Open, `.tabs`/`.tab-btn`-styled segmented pill) in the header, persisted to `localStorage` and threaded into every request, plus a `.gk-chip` on a flagged message — coordinated with the parallel rich-markdown work (different regions of the same file). 453/453 backend suite green (was 435; +18), `ruff check`/`ruff format --check`/`pyright` clean, `npm run lint` clean. `npm run build` blocked by an unrelated, still-in-flight `prismjs` typing gap in the parallel markdown work (`web/src/markdown/prism.ts`) — confirmed zero errors trace to this task's own files. `.env.example`/`docker-compose.yml` parity extended (`ANSWER_GROUNDING_DEFAULT`). Live grounding-mode verify not exercised this pass. See D46. |
| 2026-07-05 | (pending) | **T11 rich markdown chat rendering, D47:** new `web/src/markdown/{ChatMarkdown,CodeBlock,MermaidBlock,prismBash}` — `remark-gfm` for real tables/GFM, `prism-react-renderer` for highlighted+copyable fenced code (own `overflow-x:auto` box, the actual fix for the reported `docker-compose.yml`-drags-the-chat-sideways bug), a lazily `import('mermaid')`-ed `MermaidBlock` (confirmed zero bytes on initial load via `dist/index.html` — mermaid's whole chunk graph, including its own heavy lazy deps like cytoscape/katex, is never referenced there). Two real CSS-cascade bugs found and fixed during live verification, neither caught by build/lint: `.recap`'s new `overflow-wrap: anywhere` broke `white-space: pre` code blocks (Chrome honors `anywhere` even under `pre`), fixed with an explicit `overflow-wrap: normal` on `.code-block-pre`/table cells; and a pre-existing unrelated `.token { display: flex }` class (the header's bearer-token input row) collided with `prism-react-renderer`'s own `class="token ..."` convention on every highlighted span, putting each token on its own row — fixed by scoping `.code-block-pre .token { display: inline }`. A hand-built minimal-Prism-instance bundle-size optimization was tried and measured WORSE (main chunk +34 kB raw over the simple default) since `Highlight`/`themes` always bundle prism-react-renderer's own vendored languages regardless of a custom `prism` prop — reverted in favor of the simple default bundle plus a small hand-written bash grammar (bash/shell isn't in prism-react-renderer's default set). `npm run build`/`lint` clean (also resolves D46's noted in-flight `prism.ts` typing gap — that file no longer exists). Bundle: main chunk 352.25 kB/107.50 kB gzip → 481.47 kB/148.38 kB gzip (+40.88 kB gzip: ~12.1 kB for GFM, ~28.3 kB for the highlighter); CSS +0.33 kB gzip; mermaid +0 bytes on initial load. Live-verified (`sift-web-wp2`, scripted-SSE harness, headless `google-chrome` via Playwright — `claude-in-chrome` MCP unreachable this session): a table + yaml + python + mermaid fence all in one message, table/code/mermaid all render correctly, copy button verified via clipboard readback, `chat-thread` never gains a horizontal scrollbar, mermaid loads via a genuinely separate chunk request. See D47. |
| 2026-07-05 | (pending) | **T12 SSE finalization + structured grounding segments, D48:** Quentin's live BUG-1 (hybrid-mode Chat hung on "thinking..." forever after a specific query, answer only appeared after a refresh) and BUG-2 (that same mixed grounded/general-knowledge answer showed no visible marking). Root cause of BUG-1, found with evidence: `AnswerPipeline.run`'s tool-calling loop only caught `TimeoutError`, so a genuine `httpx.HTTPStatusError: 429` from real Mistral escaped uncaught mid-loop, crashing `StreamingResponse` after headers were already flushed — no terminal `"done"` frame, and `Chat.tsx` only cleared `streaming` in the `"done"` branch, so the turn stuck forever; reproduced 3/4 via `curl -N` (truncated response, exit 18) and confirmed in the engine journal, then fired AGAIN live during this pass's own re-verify and was caught cleanly by the fix. Fixed with defense in depth: `AnswerPipeline.run`'s loop + post-answer bookkeeping now wrapped in a broad `try/except Exception` (never just `TimeoutError`), always falling through to `truncated=True` + the closing `answer_delta`/`sources`/`grounding`/`done` yields; `api/v1.py::_sse_events` adds an independent second line of defense forcing a synthetic `"done"` frame if the pipeline's generator somehow still didn't; `Chat.tsx::send()` force-finalizes any turn still marked `streaming` once `readSse()` returns, for any reason. BUG-2 + API-strictness: new `pipelines/answer.py::_split_grounding_segments` splits the answer into ordered `{"text","kind":"grounded"|"general_knowledge"}` segments on marker boundaries (handles both inline same-line mixing and one-marker-per-bullet-line); `"strict"` keeps the same structural one-segment guarantee; `from_general_knowledge` now derives from `segments`. New `"grounding"` event field `segments`, new `api.schemas.GroundingSegment`, new `AnswerResponse.grounding_segments`. `Chat.tsx` renders segments individually, with a `general_knowledge` segment getting a `.gk-segment` wrapper (purple accent, left border, "GENERAL KNOWLEDGE" tag) — the message-level `.gk-chip` kept unchanged per Quentin's ask. 460/460 full suite green (was 453; +7 net), `ruff check`/`ruff format --check`/`pyright` clean, `npm run build`/`lint` clean. Live-verified (fresh `sift-engine-wp2`, real Mistral, headless `google-chrome` via Playwright — `claude-in-chrome` MCP unreachable): the exact repro query run 3× in hybrid mode, all 3 finalized cleanly (one budget-truncated, one hit the live 429 again and still finalized), non-stream `curl` confirmed `grounding_segments` with correct kinds, purple marking confirmed via a scripted-SSE-response harness (same convention as T11) driving the real `Chat.tsx` code. Screenshots: `01-hybrid-completed.png`, `02-general-knowledge-marked.png`. See D48. |
| 2026-07-05 | (pending) | **T13 parsing/chunking quality, D50 (CROSS-BOUNDARY on Arthur's `adapters/parsing/markitdown.py` + `adapters/chunking/token.py`):** a root-cause investigation (Chat UI "p. 1" badge / snippet-truncation mismatch / a real Acme re-ingest) surfaced two independent quality bugs, both confirmed against real files. `MarkitdownParser` gains a narrow, xlsx-only post-parse cleanup (`_strip_xlsx_nan_fillers`) blanking a markdown-table cell only when its entire trimmed content is exactly `"NaN"` (markitdown's xlsx converter is `pandas.read_excel(...).to_html()`, whose `na_rep` default renders every empty cell as literal `"NaN"` text) — chosen over bypassing markitdown's `XlsxConverter` with a Condense-owned reimplementation, as the lower-risk option (never touches markitdown's own multi-sheet/table-rendering path). `TokenChunker` gains a configurable `chunk_min_chars` floor (`Settings.chunk_min_chars`, default 24, `Field(ge=1)`, threaded through `factory.py`, `.env.example`/`docker-compose.yml` parity) that drops (never merges) any token window whose decoded, whitespace-collapsed text falls below it — indices stay contiguous `0..n-1` over the emitted chunks exactly as the pre-existing empty-window skip already did, verified safe against the store's real `PRIMARY KEY (tenant, source_hash, idx)` schema. Both fixes require an explicit delete + re-ingest to take effect on already-indexed documents (exact-hash dedup skips re-parsing unchanged bytes). Acceptance evidence: the two real motivating Acme xlsx files now parse with zero "NaN" occurrences (was 2,904/2,994), real content confirmed still present. 467/467 tests green (was 460; +7), ruff/pyright clean. See D50. |
| 2026-07-05 | (pending) | **T14 source-card UI quality, D49:** new shared `web/src/sourceSnippet.tsx` (`showPageBadge`, `collapseWhitespace`, `highlightQueryTerms`) consumed by both `Search.tsx` and `Chat.tsx`'s `SourcesPanel` so a citation reads identically regardless of which backend path produced it. Page badge now hidden unless `page > 1` (every real source today is `page === 1`, confirmed against live data — self-activates once a paginated parser lands). Chat's raw `text[:200]` snippet (`pipelines/answer.py::_merge_sources`) is whitespace-collapsed on the frontend rather than editing that co-owned pipeline file mid-slice (T13's agent was working nearby); idempotent, so `/search`'s already-server-collapsed snippet is unaffected. Query-term highlighting: unicode-aware, whole-word-ish (lookaround boundaries, not `\b`, so accented Spanish-corpus text matches correctly), stopword/short-token-filtered, built as React nodes (`text.split(regex)`) rather than `dangerouslySetInnerHTML` — can't become a markup-injection vector. `Chat.tsx` gained `AssistantTurn.question` (the turn's own query, for per-turn highlighting); `Search.tsx` gained its own `queriedText` state (decoupled from the live input box) for the same reason. `npm run build`/`npm run lint` clean. **Live browser verification interrupted mid-pass, then completed:** the host entered a severe, sustained system-wide OOM-kill storm mid-session (`earlyoom` killing `python`/`chrome` processes every 1-4s continuously for 10+ minutes, confirmed via syslog; `sift-engine-wp2`'s systemd restart counter climbed from 15 to 70+ during this pass alone) — every headless-Chrome attempt during the storm (`claude-in-chrome` MCP unreachable this session, playwright-core fallback per usual convention) crashed before it could paint, and even plain `curl` to the live engine became unreliable. While paused, verified by `tsc`-compiling the REAL `sourceSnippet.tsx` (not a reimplementation) and exercising it via `react-dom/server` against REAL source records captured from the live engine (a persisted "NothingAD and similar projects overview" conversation) moments before the storm made the network unreliable: `showPageBadge` correctly `false` for every real (`page===1`) source, `true` for a `page===2` sanity case; `collapseWhitespace` collapses/trims correctly; `highlightQueryTerms` correctly bolds real occurrences of "NothingAD"/"infrastructure" while correctly NOT cross-matching "Nothingall" (substring look-alike) or "preinfrastructure" (whole-word boundary check) — all targeted assertions passed. The storm eased within the session (confirmed via a dropping `earlyoom` kill rate and both `sift-web-wp2`/`sift-engine-wp2` healthy again); a real headless-Chrome pass then completed cleanly against the live app, confirming all three requirements visually: zero page badges, single-line collapsed snippets, and "NothingAD" bolded in the app's purple accent on a real Chat turn's sources, plus the same badge/whitespace behavior on a fresh real `/search` call. Screenshots: `01-no-page-badge.png`, `02-snippet-clean.png`, `03-highlight.png`. This OOM storm is still flagged as a genuine host-level incident worth Quentin's attention independent of this task (see D49 for the full account). See D49. |
| 2026-07-05 | (pending) | **T15 BUG-A/BUG-B, D51:** Quentin's live BUG-A (Strict pill active, request body confirmed `grounding:"strict"` sent, yet the answer literally leaked a `"[General knowledge]"`-prefixed competitor list) and BUG-B (switching the pill mid-conversation made a prior message's purple marking vanish). BUG-A's suspected root cause — a stale frontend grounding value — was DISPROVED by a captured-request-body repro (both hybrid and strict turns sent the correct, currently-selected mode; no frontend fix needed); the real cause was that D48's strict guarantee only covered the `from_general_knowledge` flag, never the answer text, so a history-primed completer could still leak real general-knowledge prose verbatim. Fixed: `pipelines/answer.py` now replaces the WHOLE answer with a fixed abstention (`_STRICT_ABSTENTION_TEXT`) whenever the `"[general knowledge]"` marker appears in a strict-mode answer, before segmenting/persisting/streaming. BUG-B's root cause: a plain pill click never touched prior turns' in-memory state (already correct) — the actual trigger was any `<Chat>` remount (tab switch, History reopen, page reload) refetching the conversation, which reset every historical turn's grounding to "unknown" because `ConversationStore.append_turn` never persisted it at all (D48's own deferred scope cut). Fixed: `ConversationTurn`/`ConversationStore.append_turn` gain `grounding_used`/`from_general_knowledge`/`grounding_segments` (both `Fake`/`LibSQL` adapters, 3 new ALTER-if-missing columns), `AnswerPipeline.run` persists them on the same call that stores the answer text (the abstention, never the leaked content), `GET /v1/conversations/{id}`/`Chat.tsx` render each turn from its own persisted data instead of nulling it out on reload. 475/475 full suite green (was 467; +8), ruff/pyright clean, `npm run build`/`lint` clean. Live-verified (fresh `sift-engine-wp2`, real Mistral, request bodies captured before+after): hybrid purple marking appears; switching to Strict keeps the prior message's marking both in-session AND after a full tab-switch remount (the actual BUG-B regression test); two fresh strict-mode general-knowledge questions both come back clean (one caught-and-replaced leak attempt, one honest model abstention), zero literal marker/company-list leakage, confirmed via captured request bodies showing `grounding:"strict"` genuinely sent both times. Screenshots: `01-hybrid-purple.png`, `02-switched-strict-purple-persists.png`, `02b-purple-persists-after-remount.png`, `03-strict-abstains.png`. See D51. |

## 7. Decisions

- Cross-boundary touches flagged upfront in `docs/channel/from-quentin.md` (this WP's
  announcement): `core/types.py` metadata field (additive), new `ToolCompleter` port
  (additive), libSQL store metadata column + filters, `agent/` parsing guards + exclude-files.
  Formal `DECISIONS.md` entries land per-task as forks are actually taken (T1 onward) —
  this doc records the *design*, `DECISIONS.md` records the *forks taken while building it*.
- T13 (D50) is a further cross-boundary touch, flagged in its own `docs/channel/from-quentin.md`
  update rather than upfront (it was found mid-WP by investigation, not planned at kickoff):
  `adapters/parsing/markitdown.py` and `adapters/chunking/token.py`, both Arthur-owned.
- T14 (D49) is Dev-B-only (`web/` files) — no cross-boundary touch, no channel update needed.
- T15 (D51) is Dev-B-only (`pipelines/answer.py`, `core/types.py`, `adapters/conversation/*`,
  `api/{schemas,v1}.py`, `web/`) — no cross-boundary touch, no channel update needed.

## 8. Changelog

- v0.2.0 — pending (Toolbox + Answer).
