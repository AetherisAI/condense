"""Public API request/response schemas (README §8).

Pydantic lives here (the api layer), never in ``core``. These DTOs are the frozen HTTP
contract; the routes layer maps the domain :class:`~sift.core.types.Hit` onto ``Source``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


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
    """A single citation: where the answer came from and how relevant it scored."""

    path: str
    page: int
    score: float


class SearchResponse(BaseModel):
    """Response for ``GET /search`` — the recap plus its source citations."""

    summary: str
    sources: list[Source]


class HealthResponse(BaseModel):
    """Response for ``GET /healthz`` — liveness plus the pinned embedding model."""

    status: str = "ok"
    embed_model: str | None = None
