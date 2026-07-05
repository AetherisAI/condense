"""The ``/v1`` surface (WP v0.2.0 "Toolbox + Answer") — additive, beside the existing routes.

Mounted alongside ``api.routes.router`` in ``api/main.py``; nothing on the existing
``/search``/``/ingest``/``/documents``/``/healthz`` routes changes shape. T1 landed the
JSON-ingest sibling of the existing multipart ``POST /ingest``; T2 adds the toolbox routes
(``/v1/tools/*``) — every one a thin renderer over the shared
:class:`~sift.pipelines.tools.ToolRegistry` (``Container.tools``), never a parallel code path.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from sift.api.deps import get_container, resolve_tenant
from sift.api.routes import _log_ingest_outcomes
from sift.api.schemas import (
    AnswerRequest,
    AnswerResponse,
    ConversationDeleteResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationSummary,
    ConversationTurnOut,
    DocumentIngestRequest,
    DocumentSummary,
    GroundingSegment,
    IngestFileResult,
    IngestStatus,
    Source,
    ToolChunk,
    ToolChunksResponse,
    ToolDocumentsResponse,
    ToolSchemaResponse,
    ToolSearchHit,
    ToolSearchRequest,
    ToolSearchResponse,
)
from sift.core.errors import ModelPinMismatch
from sift.core.hashing import content_hash
from sift.core.types import Chunk, Hit
from sift.factory import Container
from sift.pipelines.answer import AnswerPipeline

router = APIRouter(prefix="/v1")
logger = logging.getLogger(__name__)


def _known_grounding_mode(value: str | None) -> Literal["strict", "hybrid", "open"] | None:
    """Narrow a persisted ``ConversationTurn.grounding_used`` (plain ``str | None`` — core types
    stay loosely typed, same as ``role: str``) into the API schema's ``Literal`` (D51) — defends
    against a `None`/legacy/corrupted row the same way a bad value anywhere else in this module
    degrades rather than 500s, instead of ever raising a pydantic validation error on a read."""
    if value == "strict":
        return "strict"
    if value == "hybrid":
        return "hybrid"
    if value == "open":
        return "open"
    return None


def _validate_modified_at(value: str | None, filename: str) -> str | None:
    """Validate a single ISO-8601 ``modified_at`` value; drop (with a WARNING) if invalid.

    Mirrors ``routes._parse_modified_at``'s per-value validation (A1) for this route's single
    ``modified_at`` string, so a corrupted value can never be stored raw and later out-rank a
    real date (see ``pipelines.search._is_newer``).
    """
    if value is None:
        return None
    try:
        datetime.fromisoformat(value)
    except ValueError:
        logger.warning(
            "v1 ingest modified_at invalid for file=%r value=%r; dropping", filename, value
        )
        return None
    return value


@router.post("/documents")
async def ingest_json_document(
    body: DocumentIngestRequest,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> IngestFileResult:
    """JSON ingest of one inline text document — the non-multipart sibling of ``POST /ingest``.

    Wraps ``body.text`` as a single-file batch through the same :class:`~sift.pipelines.
    ingest.SupportsIngest` seam, threading the optional ``metadata``/``modified_at`` the same
    way the multipart route threads its per-filename maps (D28), just keyed to this one
    synthesized filename. Auth is the same bearer → tenant chokepoint (``resolve_tenant``) as
    every other route — no separate auth path for the JSON surface.
    """
    data = body.text.encode("utf-8")
    filename = body.filename or f"note-{content_hash(data)[:8]}.txt"
    mtime = _validate_modified_at(body.modified_at, filename)
    mtimes = {filename: mtime} if mtime is not None else None
    metadata = {filename: body.metadata} if body.metadata else None
    try:
        (outcome,) = await container.ingest.ingest(
            [(filename, data)], tenant, modified_at=mtimes, metadata=metadata
        )
    except ModelPinMismatch as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    _log_ingest_outcomes([outcome], tenant)
    return IngestFileResult(
        path=outcome.path,
        status=IngestStatus(outcome.status),
        content_hash=outcome.content_hash,
        chunks=outcome.chunks,
        detail=outcome.detail,
    )


def _hit_to_schema(hit: Hit) -> ToolSearchHit:
    return ToolSearchHit(
        text=hit.text,
        source_path=hit.source_path,
        page=hit.page,
        source_hash=hit.source_hash,
        index=hit.index,
        score=hit.score,
        modified_at=hit.modified_at,
        metadata=hit.metadata,
    )


def _chunk_to_schema(chunk: Chunk) -> ToolChunk:
    return ToolChunk(
        index=chunk.index,
        page=chunk.page,
        text=chunk.text,
        source_path=chunk.source_path,
        modified_at=chunk.modified_at,
        metadata=chunk.metadata,
    )


def _parse_metadata_query(raw: str | None) -> dict[str, str] | None:
    """Parse a ``GET`` query param carrying a JSON ``{key: value}`` metadata-equality filter.

    Tolerates junk the same way ``routes._parse_modified_at``'s envelope check does: a
    malformed or non-object value is treated as "no filter" rather than a 422 — the filter is
    best-effort narrowing, not a required contract on this GET route.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): str(value) for key, value in parsed.items()}


@router.post("/tools/search")
async def tools_search(
    body: ToolSearchRequest,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> ToolSearchResponse:
    """The toolbox's raw-retrieval primitive: embed → ``store.search`` — NO recap, NO LLM.

    Renders straight off :class:`~sift.pipelines.tools.ToolRegistry` (``Container.tools``), the
    same registry the (future) ``/v1/answer`` tool loop and ``GET /v1/tools/schema`` render
    from — never a parallel search code path.
    """
    args = body.model_dump()
    hits = await container.tools.call("search", args, tenant)
    return ToolSearchResponse(hits=[_hit_to_schema(hit) for hit in hits])


@router.get("/tools/documents")
async def tools_documents(
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
    limit: int = 100,
    offset: int = 0,
    metadata: str | None = None,
) -> ToolDocumentsResponse:
    """Paginated document listing, optionally narrowed by a JSON ``metadata`` query param."""
    args = {"limit": limit, "offset": offset, "metadata": _parse_metadata_query(metadata)}
    result = await container.tools.call("list_documents", args, tenant)
    documents = [
        DocumentSummary(
            path=doc.source_path,
            source_hash=doc.source_hash,
            chunks=doc.chunks,
            modified_at=doc.modified_at,
            indexed_at=doc.indexed_at,
        )
        for doc in result["documents"]
    ]
    return ToolDocumentsResponse(
        documents=documents, total=result["total"], limit=result["limit"], offset=result["offset"]
    )


@router.get("/tools/documents/{source_hash}/chunks")
async def tools_document_chunks(
    source_hash: str,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> ToolChunksResponse:
    """One document's chunks, ordered by ``index`` — empty when the store can't do chunk access."""
    chunks = await container.tools.call("get_document_chunks", {"source_hash": source_hash}, tenant)
    return ToolChunksResponse(
        source_hash=source_hash, chunks=[_chunk_to_schema(chunk) for chunk in chunks]
    )


@router.get("/tools/schema")
async def tools_schema(
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> ToolSchemaResponse:
    """Machine-readable manifest of every registered tool, generated FROM the registry.

    Bearer-authed like every other ``/v1`` route: this reveals the shape of internal tools, so
    no unauthenticated introspection. ``PATCH /settings`` is never registered in
    :class:`~sift.pipelines.tools.ToolRegistry` and so can never appear here (D38).
    """
    registry = container.tools
    manifest: dict[str, Any] = registry.to_json_schema_manifest()
    return ToolSchemaResponse(openai_functions=registry.to_openai_functions(), json_schema=manifest)


# --- POST /v1/answer -------------------------------------------------------------------


def _sse_frame(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _sse_events(
    answer: AnswerPipeline, body: AnswerRequest, tenant: str
) -> AsyncIterator[str]:
    """Render :meth:`AnswerPipeline.run`'s events as ``text/event-stream`` frames, in order.

    D48 belt-and-suspenders: ``AnswerPipeline.run`` already guarantees it always reaches
    ``"done"`` internally, but this loop is wrapped too so that ANY failure strictly between
    yielding an event and this frame reaching the wire (e.g. ``json.dumps`` choking on some
    unanticipated payload) still forces a terminal ``"done"`` frame onto the stream — the Chat
    UI relies on ``"done"`` (or the stream simply closing, as a second safety net) to stop
    showing "thinking" and re-enable input; a stream that dies silently mid-flight with no
    terminal frame is exactly BUG-1 (D48).
    """
    done_sent = False
    try:
        async for event in answer.run(
            body.message,
            tenant,
            conversation_id=body.conversation_id,
            format=body.format,
            json_schema=body.json_schema,
            grounding=body.grounding,
        ):
            if event.type == "done":
                done_sent = True
            yield _sse_frame(event.to_dict())
    except Exception:
        logger.warning(
            "SSE stream failed after emitting some events; forcing a terminal 'done' frame",
            exc_info=True,
        )
    finally:
        if not done_sent:
            yield _sse_frame(
                {"type": "done", "conversation_id": body.conversation_id or "", "truncated": True}
            )


@router.post("/answer", response_model=None)
async def answer(
    body: AnswerRequest,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> AnswerResponse | StreamingResponse:
    """The reference tool-calling agent (WP v0.2.0 T3, D40) — proves the toolbox works end to
    end through whichever ``ToolCompleter`` is configured. Every capability it uses comes from
    :class:`~sift.pipelines.tools.ToolRegistry` (``container.answer``'s own boundary rule,
    ``tests/pipelines/test_answer_boundary.py``) — this route is a thin renderer, same as every
    other ``/v1`` route.
    """
    if body.stream:
        return StreamingResponse(
            _sse_events(container.answer, body, tenant), media_type="text/event-stream"
        )

    answer_text = ""
    conversation_id = body.conversation_id or ""
    truncated = False
    trace: list[dict[str, Any]] = []
    sources: list[Source] = []
    grounding_used = body.grounding or container.settings.answer_grounding_default
    from_general_knowledge = False
    grounding_segments: list[GroundingSegment] = []
    async for event in container.answer.run(
        body.message,
        tenant,
        conversation_id=body.conversation_id,
        format=body.format,
        json_schema=body.json_schema,
        grounding=body.grounding,
    ):
        rendered = event.to_dict()
        if event.type == "answer_delta":
            answer_text += rendered["text"]
            continue  # collapsed into `answer`, not part of the non-stream trace
        if event.type == "sources":
            sources = [Source(**item) for item in rendered["items"]]
        if event.type == "grounding":
            grounding_used = rendered["grounding_used"]
            from_general_knowledge = rendered["from_general_knowledge"]
            grounding_segments = [
                GroundingSegment(**segment) for segment in rendered.get("segments", [])
            ]
        if event.type == "done":
            conversation_id = rendered["conversation_id"]
            truncated = rendered["truncated"]
        trace.append(rendered)
    return AnswerResponse(
        answer=answer_text,
        format=body.format,
        conversation_id=conversation_id,
        trace=trace,
        truncated=truncated,
        sources=sources,
        grounding_used=grounding_used,
        from_general_knowledge=from_general_knowledge,
        grounding_segments=grounding_segments,
    )


# --- GET/DELETE /v1/conversations — chat-session management (WP v0.2.0 T6, D42) -------------
#
# Plain REST over `Container.conversations` directly — deliberately NOT `ToolRegistry` tools:
# these manage the CHAT SESSION (list/reopen/delete a conversation), not a corpus capability
# any tool-calling consumer should be able to invoke on itself mid-loop. `tests/pipelines/
# test_tools_schema.py` asserts the registry still exposes exactly the 3 corpus tools.


@router.get("/conversations")
async def list_conversations(
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
    limit: int = 50,
    offset: int = 0,
) -> ConversationListResponse:
    """Past conversations, newest-updated first — the History panel's list."""
    metas = await container.conversations.list_conversations(tenant, limit=limit, offset=offset)
    return ConversationListResponse(
        conversations=[
            ConversationSummary(
                conversation_id=meta.conversation_id,
                title=meta.title,
                updated_at=meta.updated_at,
                turn_count=meta.turn_count,
            )
            for meta in metas
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> ConversationDetailResponse:
    """One conversation's meta + every turn (incl. each assistant turn's persisted sources) —
    reopening it from the History panel refetches this instead of replaying the tool loop."""
    detail = await container.conversations.get_conversation(tenant, conversation_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found")
    return ConversationDetailResponse(
        conversation_id=detail.meta.conversation_id,
        title=detail.meta.title,
        created_at=detail.meta.created_at,
        updated_at=detail.meta.updated_at,
        turns=[
            ConversationTurnOut(
                role=turn.role,
                content=turn.content,
                turn=turn.turn,
                created_at=turn.created_at,
                sources=[Source(**item) for item in turn.sources] if turn.sources else None,
                grounding_used=_known_grounding_mode(turn.grounding_used),
                from_general_knowledge=turn.from_general_knowledge,
                grounding_segments=[
                    GroundingSegment(**segment) for segment in (turn.grounding_segments or [])
                ],
            )
            for turn in detail.turns
        ],
    )


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    container: Annotated[Container, Depends(get_container)],
    tenant: Annotated[str, Depends(resolve_tenant)],
) -> ConversationDeleteResponse:
    """Delete one conversation — idempotent, so deleting an unknown id 200s the same way."""
    await container.conversations.delete_conversation(tenant, conversation_id)
    return ConversationDeleteResponse(conversation_id=conversation_id)
