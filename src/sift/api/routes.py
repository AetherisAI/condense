"""HTTP routes — the thin surface over the query and ingest pipelines (README §3).

Every handler pulls the wired :class:`~sift.factory.Container` from :func:`get_container` and
delegates to a pipeline; it never constructs an adapter (the dependency rule). ``/healthz`` is
open; everything else sits behind :func:`resolve_tenant`, the single bearer → tenant chokepoint.
``POST /ingest`` maps each engine :class:`~sift.pipelines.ingest.IngestOutcome` onto the API
schema and surfaces a :class:`~sift.core.errors.ModelPinMismatch` as HTTP 409.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status

from sift.api.deps import get_container, resolve_tenant
from sift.api.health import gather_components
from sift.api.schemas import (
    DeleteDocumentResponse,
    DocumentsResponse,
    DocumentSummary,
    HealthResponse,
    IngestFileResult,
    IngestResponse,
    IngestStatus,
    ManifestResponse,
    SearchResponse,
    SettingsPatch,
    StatusResponse,
)
from sift.config import Settings
from sift.core.errors import ModelPinMismatch
from sift.factory import Container, build_container
from sift.pipelines.documents import SupportsDocumentAdmin

router = APIRouter()

# Never serialize these back to a client — only whether they are configured.
_SECRET_KEYS = frozenset({"turso_auth_token", "embed_api_key", "llm_api_key", "ingest_token"})


def _redacted_settings(settings: Settings) -> dict[str, object]:
    """The effective config with every secret replaced by a presence flag ("set"/None)."""
    out: dict[str, object] = {}
    for key, value in settings.model_dump().items():
        out[key] = ("set" if value else None) if key in _SECRET_KEYS else value
    return out


async def _status_response(container: Container, tenant: str) -> StatusResponse:
    """Build the shared /status payload: health, per-component probes, redacted config."""
    settings = container.settings
    components = await gather_components(settings, container.store, tenant)
    return StatusResponse(
        status="ok",
        embed_model=settings.embed_model,
        components=components,
        settings=_redacted_settings(settings),
    )


@router.get("/healthz")
async def healthz(
    container: Annotated[Container, Depends(get_container)],
) -> HealthResponse:
    """Liveness plus the configured embedding model — no auth (README §3)."""
    return HealthResponse(status="ok", embed_model=container.settings.embed_model)


@router.get("/status")
async def status_(
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> StatusResponse:
    """Health + the effective config for the debug panel — bearer-gated, secrets redacted."""
    return await _status_response(container, tenant)


@router.patch("/settings")
async def update_settings(
    patch: SettingsPatch,
    request: Request,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> StatusResponse:
    """Edit safe tuning settings on the fly (bearer-gated).

    Only the allowlisted fields on :class:`SettingsPatch` are accepted (others → 422). The
    new settings rebuild the wired container in place, so the change applies to the next
    request — no restart. Returns the fresh status (with the updated, redacted config).
    """
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no settings given")
    updated = container.settings.model_copy(update=updates)
    new_container = build_container(updated)
    request.app.state.container = new_container
    return await _status_response(new_container, tenant)


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
    """Parse → chunk → embed → upsert each uploaded file; 409 on a model-pin mismatch.

    Files are streamed to the pipeline one at a time (read → hand off → release) rather than all
    read into a single in-memory list, so a large multi-file upload doesn't spike RAM to the sum of
    every file — peak stays at roughly one file plus its chunks.
    """

    async def _stream() -> AsyncIterator[tuple[str, bytes]]:
        for file in files:
            data = await file.read()
            try:
                yield (file.filename or "", data)
            finally:
                await file.close()  # release the spooled upload before reading the next

    try:
        outcomes = await container.ingest.ingest(_stream(), tenant)
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


@router.get("/documents")
async def list_documents(
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> DocumentsResponse:
    """The tenant's ingested source files (one row per file) — for the admin/management panel.

    Depends on the structural :class:`~sift.pipelines.documents.SupportsDocumentAdmin` seam, not a
    concrete store: a store that can't enumerate documents degrades to ``supported=false`` rather
    than erroring, so the UI just hides the panel.
    """
    store = container.store
    if not isinstance(store, SupportsDocumentAdmin):
        return DocumentsResponse(tenant=tenant, documents=[], supported=False)
    docs = await store.list_documents(tenant)
    return DocumentsResponse(
        tenant=tenant,
        documents=[
            DocumentSummary(path=d.source_path, source_hash=d.source_hash, chunks=d.chunks)
            for d in docs
        ],
    )


@router.delete("/documents/{source_hash}")
async def delete_document(
    source_hash: str,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> DeleteDocumentResponse:
    """Drop an ingested file's chunks by its ``source_hash`` — 501 if the store can't do admin."""
    store = container.store
    if not isinstance(store, SupportsDocumentAdmin):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="document admin not supported by the configured store",
        )
    deleted = await store.delete_document(source_hash, tenant)
    return DeleteDocumentResponse(tenant=tenant, source_hash=source_hash, deleted_chunks=deleted)
