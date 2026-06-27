"""API request/response schemas (pydantic) — the HTTP boundary contract."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Source(BaseModel):
    path: str
    page: int | None = None
    score: float


class SearchResponse(BaseModel):
    summary: str
    sources: list[Source]


class IngestStatus(str, Enum):
    indexed = "indexed"
    skipped = "skipped"
    failed = "failed"


class IngestFileResult(BaseModel):
    filename: str
    status: IngestStatus
    detail: str | None = None


class IngestResponse(BaseModel):
    files: list[IngestFileResult]


class ManifestResponse(BaseModel):
    tenant: str
    hashes: list[str]


class HealthResponse(BaseModel):
    status: str
    embed_model: str
