"""HTTP routes — the thin surface over the query and ingest pipelines (README §3).

Every handler pulls the wired :class:`~sift.factory.Container` from :func:`get_container` and
delegates to a pipeline; it never constructs an adapter (the dependency rule). ``/healthz`` is
open; everything else sits behind :func:`resolve_tenant`, the single bearer → tenant chokepoint.
``POST /ingest`` maps each engine :class:`~sift.pipelines.ingest.IngestOutcome` onto the API
schema and surfaces a :class:`~sift.core.errors.ModelPinMismatch` as HTTP 409.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Mapping
from datetime import datetime
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status

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
    Source,
    StatusResponse,
)
from sift.config import Settings
from sift.core.errors import ModelPinMismatch
from sift.factory import Container, build_container
from sift.pipelines.documents import SupportsDocumentAdmin
from sift.pipelines.ingest import IngestOutcome

router = APIRouter()
logger = logging.getLogger(__name__)

# Never serialize these back to a client — only whether they are configured. ``auth_tokens``
# holds the per-consumer bearer credentials verbatim ("name:token,...") and authenticates every
# protected route exactly like ``ingest_token``, so it must be redacted too — otherwise any
# authenticated consumer could read every other consumer's plaintext token off GET /status.
_SECRET_KEYS = frozenset(
    {
        "turso_auth_token",
        "embed_api_key",
        "llm_api_key",
        "ingest_token",
        "ocr_api_key",
        "auth_tokens",
    }
)


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

    The pipeline returns a stdlib-only :class:`~sift.core.types.SearchOutcome` (the dependency
    rule: pipelines never import ``sift.api``) — mapped 1:1 onto the HTTP ``SearchResponse``/
    ``Source`` schemas here, so the JSON shape is unchanged.
    """
    outcome = await container.search.search(q, tenant, recap=recap)
    return SearchResponse(
        summary=outcome.summary,
        sources=[
            Source(
                path=source.path,
                page=source.page,
                score=source.score,
                snippet=source.snippet,
                index=source.index,
                metadata=source.metadata,
            )
            for source in outcome.sources
        ],
    )


@router.get("/ingest/manifest")
async def ingest_manifest(
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> ManifestResponse:
    """The tenant's known content-hashes (sorted) — backs the agent's dedup diff."""
    hashes = sorted(await container.store.known_hashes(tenant))
    return ManifestResponse(tenant=tenant, hashes=hashes)


def _parse_modified_at(raw: str | None) -> dict[str, str] | None:
    """Parse the optional ``modified_at`` form field (a JSON ``{name: iso}`` map); tolerate junk.

    A malformed or non-object *envelope* is ignored (treated as "no mtimes") rather than failing
    the whole upload — the recency hint is best-effort, never a reason to reject good documents.
    Each individual *value* is validated as a real ISO-8601 timestamp (``datetime.fromisoformat``,
    README/A1): a garbage value like ``"corrupted-not-a-date"`` is dropped with a WARNING naming
    the file, rather than stored and later compared as a raw string (A1 — the old string
    comparison let a corrupted value out-rank a real date; see ``pipelines.search._is_newer``).
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    mtimes: dict[str, str] = {}
    for key, value in parsed.items():
        if value is None:
            continue
        text = str(value)
        try:
            datetime.fromisoformat(text)
        except ValueError:
            logger.warning("ingest modified_at invalid for file=%r value=%r; dropping", key, text)
            continue
        mtimes[str(key)] = text
    return mtimes


# F4 (clickable-citations dead-end audit, security): a per-file ``metadata`` value is stored
# verbatim and, for the reserved ``source_url`` key, rendered by the web client as a clickable
# ``<a href>`` deep link (``web/src/sourceLink.ts``) — an unvalidated scheme there
# (``javascript:``, ``file:``, ``data:``, a bare ``//evil`` protocol-relative URL, ...) becomes
# an XSS/open-redirect vector the moment a citation card is clicked, and an unbounded value is
# a cheap way to bloat every citation payload. ``_MAX_METADATA_VALUE_CHARS`` bounds every
# metadata value (not just ``source_url``) at ingest — the one place malformed caller intent is
# still cheap to reject outright (see the docstring below) rather than truncate silently.
_MAX_METADATA_VALUE_CHARS = 2048
_URL_METADATA_KEY = "source_url"
_URL_METADATA_SCHEMES = frozenset({"http", "https"})


def _validate_url_metadata_value(filename: str, key: str, value: str) -> None:
    """Reject a ``source_url``-keyed metadata value that isn't a real ``http``/``https`` URL
    with a host (F4). ``urlsplit`` alone is intentionally permissive (a bare ``//evil/x`` parses
    with an empty ``scheme``, ``javascript:alert(1)`` parses with an empty ``netloc``) so both
    checks are required together — same 422-naming-file-and-key style as every other malformed-
    metadata rejection in :func:`_parse_metadata`.
    """
    parsed = urlsplit(value)
    if parsed.scheme not in _URL_METADATA_SCHEMES or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"metadata[{filename!r}][{key!r}] must be an http:// or https:// URL with a "
                f"host, got {value!r}"
            ),
        )


def validate_file_metadata(filename: str, tags: Mapping[str, Any]) -> dict[str, str]:
    """Validate ONE file's metadata dict the same way for every ingest surface: string values
    only, each at most ``_MAX_METADATA_VALUE_CHARS``, and a ``source_url`` that is a real
    http(s) URL with a host. Shared by the multipart ``POST /ingest`` (via
    :func:`_parse_metadata`) and the JSON ``POST /v1/documents`` (third-pass audit: that route
    validated nothing, so ``javascript:`` and ``file:`` URLs and 3000-char values went straight
    into the store, and it is exactly the route the desktop re-ingest uses). Returns the tags
    as ``dict[str, str]``; raises the same 422 shape either way.
    """
    out: dict[str, str] = {}
    for key, value in tags.items():
        if not isinstance(value, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"metadata[{filename!r}][{key!r}] must be a string value "
                    f"(got {type(value).__name__})"
                ),
            )
        if len(value) > _MAX_METADATA_VALUE_CHARS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"metadata[{filename!r}][{key!r}] exceeds {_MAX_METADATA_VALUE_CHARS} chars"
                ),
            )
        if key == _URL_METADATA_KEY:
            _validate_url_metadata_value(filename, key, value)
        out[str(key)] = value
    return out


def _parse_metadata(raw: str | None) -> dict[str, dict[str, str]] | None:
    """Parse the optional ``metadata`` form field: a JSON object ``{upload_name: {key: value}}``
    of per-file string tags (D28's per-file map, the same shape ``POST /v1/documents`` already
    accepts as ``DocumentIngestRequest.metadata``, keyed here to every file in the batch instead
    of just one). Reserved keys like ``source_url`` (the citation deep-link) live in here — its
    value is additionally scheme/host-validated (F4, see :func:`_validate_url_metadata_value`)
    since the web client renders it as a clickable link. Every value (any key) is also bounded
    to ``_MAX_METADATA_VALUE_CHARS``.

    Unlike ``modified_at`` (a best-effort recency hint that silently drops a bad value),
    ``metadata`` is explicit caller intent, so malformed input is a real client error: this
    raises HTTP 422 naming exactly what's wrong rather than silently ingesting the file with
    the tag dropped.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"metadata is not valid JSON: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="metadata must be a JSON object of {upload_name: {key: value}}",
        )
    result: dict[str, dict[str, str]] = {}
    for filename, tags in parsed.items():
        if not isinstance(tags, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"metadata[{filename!r}] must be an object of string key/value tags",
            )
        result[str(filename)] = validate_file_metadata(str(filename), tags)
    return result


@router.post("/ingest")
async def ingest(
    files: list[UploadFile],
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
    modified_at: Annotated[str | None, Form()] = None,
    metadata: Annotated[str | None, Form()] = None,
) -> IngestResponse:
    """Parse → chunk → embed → upsert each uploaded file; 409 on a model-pin mismatch.

    ``modified_at`` is an optional JSON object ``{upload_name: iso8601}`` of each file's
    last-modified time, sent by the agent so version-collapse can prefer the newest copy.

    ``metadata`` is an optional JSON object ``{upload_name: {key: value}}`` of per-file string
    tags (D28) — e.g. the ``source_url`` a citation card deep-links to. Values must be strings;
    a malformed envelope or a non-string value 422s the whole request (see ``_parse_metadata``)
    rather than silently dropping the tag, since a caller who sent metadata clearly wanted it
    stored. Note the store's dedup short-circuits on content hash BEFORE the upsert that would
    apply new metadata (see ``pipelines.ingest.IngestPipeline.ingest``): re-ingesting identical
    bytes with new metadata is reported as ``skipped_dedup`` and does NOT update the stored tags
    — delete the document first if the metadata must change without changing the bytes.

    Files are streamed to the pipeline one at a time (read → hand off → release) rather than all
    read into a single in-memory list, so a large multi-file upload doesn't spike RAM to the sum of
    every file — peak stays at roughly one file plus its chunks (Arthur's A12).

    Every outcome is logged server-side (README §F1/E3): a batch that comes back HTTP 200 must
    never silently hide a lost file — each failure gets its own WARNING line (path + detail),
    plus one INFO summary of the whole batch's indexed/skipped/failed counts.
    """
    mtimes = _parse_modified_at(modified_at)
    file_metadata = _parse_metadata(metadata)

    async def _stream() -> AsyncIterator[tuple[str, bytes]]:
        for file in files:
            data = await file.read()
            try:
                yield (file.filename or "", data)
            finally:
                await file.close()  # release the spooled upload before reading the next

    try:
        outcomes = await container.ingest.ingest(
            _stream(), tenant, modified_at=mtimes, metadata=file_metadata
        )
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
    _log_ingest_outcomes(outcomes, tenant)
    return IngestResponse(tenant=tenant, results=results)


def _log_ingest_outcomes(outcomes: list[IngestOutcome], tenant: str) -> None:
    """Per-file WARNING for every failure, plus one INFO summary — never a silent 200."""
    counts = {"indexed": 0, "skipped_dedup": 0, "failed": 0}
    for outcome in outcomes:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        if outcome.status == "failed":
            logger.warning(
                "ingest failed path=%r tenant=%r detail=%s", outcome.path, tenant, outcome.detail
            )
    logger.info(
        "ingest batch tenant=%r total=%d indexed=%d skipped_dedup=%d failed=%d",
        tenant,
        len(outcomes),
        counts["indexed"],
        counts["skipped_dedup"],
        counts["failed"],
    )


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
            DocumentSummary(
                path=d.source_path,
                source_hash=d.source_hash,
                chunks=d.chunks,
                modified_at=d.modified_at,
                indexed_at=d.indexed_at,
            )
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
