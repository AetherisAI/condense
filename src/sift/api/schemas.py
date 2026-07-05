"""Public API request/response schemas (README §8).

Pydantic lives here (the api layer), never in ``core``. These DTOs are the frozen HTTP
contract; the routes layer maps the domain :class:`~sift.core.types.Hit` onto ``Source``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from sift.config import get_settings


class IngestStatus(StrEnum):
    """Per-file outcome of an ingest request."""

    indexed = "indexed"
    skipped_dedup = "skipped_dedup"
    failed = "failed"


class IngestFileResult(BaseModel):
    """The result for a single uploaded file."""

    path: str
    status: IngestStatus
    content_hash: str | None = None
    chunks: int | None = None
    detail: str | None = None


class IngestResponse(BaseModel):
    """Response for ``POST /ingest`` (the request itself is multipart form-data)."""

    tenant: str
    results: list[IngestFileResult]


class ManifestResponse(BaseModel):
    """Response for ``GET /ingest/manifest`` — known content-hashes for the agent's diff."""

    tenant: str
    hashes: list[str]


class DocumentSummary(BaseModel):
    """One ingested source file in the document-admin listing (aggregated from its chunks).

    ``modified_at``/``indexed_at`` (D44, additive) are the source file's true last-modified
    time (``None`` if never provided at ingest) and when the store indexed it — the temporal
    signal a "when was this written/modified" question should be answered from, never a date
    guessed from the filename.
    """

    path: str
    source_hash: str
    chunks: int
    modified_at: str | None = None
    indexed_at: str | None = None


class DocumentsResponse(BaseModel):
    """Response for ``GET /documents`` — the tenant's ingested files.

    ``supported`` is ``False`` when the configured store does not implement the document-admin
    seam, so the UI can hide the panel instead of treating it as an error.
    """

    tenant: str
    documents: list[DocumentSummary]
    supported: bool = True


class DeleteDocumentResponse(BaseModel):
    """Response for ``DELETE /documents/{source_hash}`` — how many chunks were removed."""

    tenant: str
    source_hash: str
    deleted_chunks: int


class Source(BaseModel):
    """A single citation: where the answer came from, the matched passage, and its score."""

    path: str
    page: int
    score: float
    snippet: str = ""  # the matched passage text (truncated) — shows *where* in the doc
    index: int | None = None  # 0-based chunk ordinal within the document, when known
    metadata: dict[str, str] | None = None  # per-file tags carried from Hit.metadata, when set


class DocumentIngestRequest(BaseModel):
    """Request body for ``POST /v1/documents`` — JSON ingest of one inline text document.

    A non-multipart sibling of the existing ``POST /ingest``: the same pipeline runs on the
    encoded text of a single "file". ``text`` must be non-empty (422 on ``""``) and no longer
    than ``Settings.parse_max_chars`` (422 on oversized — the same post-parse guardrail every
    other ingest path enforces, D39/D40 amendment: an inline JSON document 422s up front instead
    of being accepted here and only failing deep inside the parse pipeline). ``filename``
    defaults to ``note-<hash8>.txt`` (derived from the content hash) when omitted.
    """

    text: str = Field(min_length=1)
    filename: str | None = None
    metadata: dict[str, str] | None = None
    modified_at: str | None = None  # ISO-8601; invalid values are dropped, never stored raw

    @field_validator("text")
    @classmethod
    def _text_within_parse_guardrail(cls, value: str) -> str:
        limit = get_settings().parse_max_chars
        if len(value) > limit:
            raise ValueError(f"text exceeds parse_max_chars ({limit} chars)")
        return value


class SearchResponse(BaseModel):
    """Response for ``GET /search`` — the recap plus its source citations."""

    summary: str
    sources: list[Source]


class ToolSearchFilters(BaseModel):
    """Search-time narrowing for ``POST /v1/tools/search`` (WP v0.2.0 T2, D38).

    Applied by the store BEFORE the ranking limit — narrows the candidate set, never a
    post-hoc filter on an already-capped top-K. ``metadata`` is equality on every given key;
    ``since``/``until`` bound the source file's ``modified_at`` (inclusive, ISO-8601).
    """

    metadata: dict[str, str] | None = None
    since: str | None = None
    until: str | None = None


class ToolSearchRequest(BaseModel):
    """Request body for ``POST /v1/tools/search`` — the toolbox's raw-retrieval primitive.

    ``k`` defaults to ``Settings.tools_search_k`` and is capped at ``Settings.tools_search_max_k``
    when omitted/oversized. Unlike ``GET /search``, there is NO recap — the caller reasons over
    the returned hits itself.
    """

    query: str = Field(min_length=1)
    k: int | None = None
    filters: ToolSearchFilters | None = None


class ToolSearchHit(BaseModel):
    """One raw ranked passage returned by ``POST /v1/tools/search`` — no recap, just the hit."""

    text: str
    source_path: str
    page: int
    source_hash: str
    index: int
    score: float
    modified_at: str | None = None
    metadata: dict[str, str] | None = None


class ToolSearchResponse(BaseModel):
    """Response for ``POST /v1/tools/search``."""

    hits: list[ToolSearchHit]


class ToolDocumentsResponse(BaseModel):
    """Response for ``GET /v1/tools/documents`` — paginated, optionally metadata-filtered."""

    documents: list[DocumentSummary]
    total: int
    limit: int
    offset: int


class ToolChunk(BaseModel):
    """One chunk of one ingested document, as returned by
    ``GET /v1/tools/documents/{source_hash}/chunks``."""

    index: int
    page: int
    text: str
    source_path: str
    modified_at: str | None = None
    metadata: dict[str, str] | None = None


class ToolChunksResponse(BaseModel):
    """Response for ``GET /v1/tools/documents/{source_hash}/chunks`` — ordered by ``index``."""

    source_hash: str
    chunks: list[ToolChunk]


class ToolSchemaResponse(BaseModel):
    """Response for ``GET /v1/tools/schema`` — the registry's manifest, in both formats.

    Generated FROM :class:`~sift.pipelines.tools.ToolRegistry`, never hand-written; ``PATCH
    /settings`` is never registered and so can never appear here (WP v0.2.0 T2, D38 — see
    ``tests/pipelines/test_tools_schema.py``).
    """

    openai_functions: list[dict[str, Any]]
    json_schema: dict[str, Any]


class AnswerRequest(BaseModel):
    """Request body for ``POST /v1/answer`` — the reference tool-calling agent (WP v0.2.0 T3).

    ``conversation_id`` threads a follow-up turn's context; omitted on the first turn (the
    server generates and returns one). ``format="json"`` constrains the final answer to
    ``json_schema`` (loose, best-effort validation — see ``pipelines/answer.py``).
    ``stream=true`` switches the response to ``text/event-stream`` SSE of the same event
    vocabulary the non-stream ``trace`` carries. ``grounding`` (D46) overrides
    ``Settings.answer_grounding_default`` for this one request; ``None`` (the default) falls
    back to the configured default — see ``pipelines/answer.py`` for what each mode means.
    """

    message: str = Field(min_length=1)
    conversation_id: str | None = None
    format: Literal["text", "json"] = "text"
    json_schema: dict[str, Any] | None = None
    stream: bool = False
    grounding: Literal["strict", "hybrid", "open"] | None = None


class GroundingSegment(BaseModel):
    """One ordered slice of ``AnswerResponse.answer`` (D48) — the structured, machine-parseable
    sibling of ``from_general_knowledge``: a consumer can tell WHICH parts of the answer are
    grounded in the ingested documents vs the model's own general/training knowledge, not just
    THAT some part is (previously only the inline literal ``"[General knowledge]"`` marker text
    itself, which every consumer would have had to re-parse independently).

    ``kind="grounded"`` in ``"strict"`` mode ALWAYS covers the whole answer as one segment — the
    same structural guarantee ``from_general_knowledge=False`` gets in strict mode, regardless
    of what the model's raw text contains. In hybrid/open, segments are split on every
    occurrence of the model's own ``"[General knowledge]"`` marker (see
    ``pipelines.answer._split_grounding_segments``); concatenating every segment's ``text`` in
    order reconstructs the answer's content (marker syntax and its immediate separators
    stripped, not a byte-exact copy of the model's raw output).
    """

    text: str
    kind: Literal["grounded", "general_knowledge"]


class AnswerResponse(BaseModel):
    """Non-streaming response for ``POST /v1/answer``.

    ``trace`` is the ordered event log minus ``answer_delta`` (collapsed into ``answer``) —
    the SAME event vocabulary the ``stream=true`` SSE response emits incrementally, so a
    non-streaming caller still gets full tool-use observability, just not incrementally.
    ``sources`` (WP v0.2.0 T6, D42) is the SAME compact citation list as the ``sources`` SSE
    event / trace entry, surfaced as its own top-level field so a caller never has to mine the
    trace for it; empty when no ``search`` tool call happened. ``grounding_used``/
    ``from_general_knowledge`` (D46) are the SAME fields the ``grounding`` SSE event carries —
    which mode actually answered this turn, and whether the answer contains any content the
    pipeline detected as drawn from the model's own knowledge rather than the corpus (always
    ``False`` in ``"strict"`` mode, regardless of what the model returned). ``grounding_segments``
    (D48) is the structured breakdown backing that boolean — see :class:`GroundingSegment`.
    """

    answer: str
    format: Literal["text", "json"]
    conversation_id: str
    trace: list[dict[str, Any]]
    truncated: bool
    sources: list[Source] = []
    grounding_used: Literal["strict", "hybrid", "open"] = "strict"
    from_general_knowledge: bool = False
    grounding_segments: list[GroundingSegment] = []


class ConversationSummary(BaseModel):
    """One row of ``GET /v1/conversations`` (WP v0.2.0 T6, D42) — no turns, just enough to
    render a History list entry. ``title`` is ``None`` until the auto-title pass fires."""

    conversation_id: str
    title: str | None = None
    updated_at: str
    turn_count: int


class ConversationListResponse(BaseModel):
    """Response for ``GET /v1/conversations`` — ordered newest-updated first."""

    conversations: list[ConversationSummary]
    limit: int
    offset: int


class ConversationTurnOut(BaseModel):
    """One turn as returned by ``GET /v1/conversations/{id}`` — ``sources`` is set only on a
    citing assistant turn (persisted alongside it, WP v0.2.0 T6, D42).

    ``grounding_used``/``from_general_knowledge``/``grounding_segments`` (D51) are the SAME
    per-turn immutable grounding fields the ``grounding`` SSE event carries live — persisted on
    the assistant turn at receive time and rendered as-is on reload, never re-derived from
    whichever grounding mode happens to be selected when the conversation is reopened. ``None``/
    ``False``/``[]`` on a user turn, or on an assistant turn from before D51.
    """

    role: str
    content: str
    turn: int
    created_at: str
    sources: list[Source] | None = None
    grounding_used: Literal["strict", "hybrid", "open"] | None = None
    from_general_knowledge: bool = False
    grounding_segments: list[GroundingSegment] = []


class ConversationDetailResponse(BaseModel):
    """Response for ``GET /v1/conversations/{id}`` — meta plus every stored turn, oldest first."""

    conversation_id: str
    title: str | None = None
    created_at: str
    updated_at: str
    turns: list[ConversationTurnOut]


class ConversationDeleteResponse(BaseModel):
    """Response for ``DELETE /v1/conversations/{id}`` — idempotent, so ``deleted`` is always
    ``True`` (the endpoint never 404s on an unknown id, matching REST DELETE idempotency)."""

    conversation_id: str
    deleted: bool = True


class HealthResponse(BaseModel):
    """Response for ``GET /healthz`` — liveness plus the pinned embedding model."""

    status: str = "ok"
    embed_model: str | None = None


class ComponentHealth(BaseModel):
    """Reachability of one configured dependency (embeddings, llm, reranker, storage)."""

    status: str  # "ok" | "down" | "not_configured"
    model: str | None = None
    detail: str | None = None


class SettingsPatch(BaseModel):
    """The allowlist of runtime-editable tuning settings (``PATCH /settings``).

    Only safe knobs that take effect by rebuilding the container — no models, base URLs,
    secrets, or store backend. ``extra="forbid"`` rejects anything off this list with 422.
    Every field is optional; only the ones sent are applied.
    """

    model_config = ConfigDict(extra="forbid")

    recap_enabled: bool | None = None
    recap_context_k: int | None = None
    recap_max_tokens: int | None = None
    recap_temperature: float | None = None
    source_snippet_chars: int | None = None
    retrieve_k: int | None = None
    final_k: int | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    rerank_strategy: Literal["none", "llm", "crossencoder"] | None = None


class StatusResponse(BaseModel):
    """Response for ``GET /status`` — health plus the effective config (secrets redacted)."""

    status: str = "ok"
    embed_model: str | None = None
    components: dict[str, ComponentHealth] = {}
    settings: dict[str, Any]
