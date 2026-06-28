"""HTTP routes — the thin surface over the query and ingest pipelines (README §3).

Every handler pulls the wired :class:`~sift.factory.Container` from :func:`get_container` and
delegates to a pipeline; it never constructs an adapter (the dependency rule). ``/healthz`` is
open; everything else sits behind :func:`resolve_tenant`, the single bearer → tenant chokepoint.
``POST /ingest`` maps each engine :class:`~sift.pipelines.ingest.IngestOutcome` onto the API
schema and surfaces a :class:`~sift.core.errors.ModelPinMismatch` as HTTP 409.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from sift.api.deps import get_container, resolve_tenant
from sift.api.schemas import (
    HealthResponse,
    IngestFileResult,
    IngestResponse,
    IngestStatus,
    ManifestResponse,
    SearchResponse,
)
from sift.core.errors import ModelPinMismatch
from sift.factory import Container

router = APIRouter()


@router.get("/healthz")
async def healthz(
    container: Annotated[Container, Depends(get_container)],
) -> HealthResponse:
    """Liveness plus the configured embedding model — no auth (README §3)."""
    return HealthResponse(status="ok", embed_model=container.settings.embed_model)


@router.get("/search")
async def search(
    q: str,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
    recap: bool | None = None,
) -> SearchResponse:
    """Embed → retrieve → rerank → recap for query ``q`` — the single best result.

    ``recap`` overrides the configured default: ``recap=false`` skips the LLM summary and
    returns just the source citation (doc + page); omitted falls back to ``RECAP_ENABLED``.
    """
    return await container.search.search(q, tenant, recap=recap)


@router.get("/ingest/manifest")
async def ingest_manifest(
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> ManifestResponse:
    """The tenant's known content-hashes (sorted) — backs the agent's dedup diff."""
    hashes = sorted(await container.store.known_hashes(tenant))
    return ManifestResponse(tenant=tenant, hashes=hashes)


@router.post("/ingest")
async def ingest(
    files: list[UploadFile],
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> IngestResponse:
    """Parse → chunk → embed → upsert each uploaded file; 409 on a model-pin mismatch."""
    payload = [(file.filename or "", await file.read()) for file in files]
    try:
        outcomes = await container.ingest.ingest(payload, tenant)
    except ModelPinMismatch as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    results = [
        IngestFileResult(
            path=outcome.path,
            status=IngestStatus(outcome.status),
            content_hash=outcome.content_hash,
            chunks=outcome.chunks,
            detail=outcome.detail,
        )
        for outcome in outcomes
    ]
    return IngestResponse(tenant=tenant, results=results)
