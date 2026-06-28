"""Public API request/response schemas (README §8).

Pydantic lives here (the api layer), never in ``core``. These DTOs are the frozen HTTP
contract; the routes layer maps the domain :class:`~sift.core.types.Hit` onto ``Source``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


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


class Source(BaseModel):
    """A single citation: where the answer came from, the matched passage, and its score."""

    path: str
    page: int
    score: float
    snippet: str = ""  # the matched passage text (truncated) — shows *where* in the doc
    index: int | None = None  # 0-based chunk ordinal within the document, when known


class SearchResponse(BaseModel):
    """Response for ``GET /search`` — the recap plus its source citations."""

    summary: str
    sources: list[Source]


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
