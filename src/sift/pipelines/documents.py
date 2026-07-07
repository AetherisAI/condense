"""The document-admin seam — list and delete ingested source files (README §3).

A capability :class:`typing.Protocol`, exactly like :class:`~sift.pipelines.ingest.SupportsIngest`:
Dev B's ``/documents`` routes depend on this structural seam, never on a concrete store, so a
store that implements it (the fake today, libSQL later) is picked up automatically and one that
doesn't degrades gracefully — the route reports it unsupported rather than failing. Ports/types
only (the dependency rule: ``pipelines`` never imports an adapter); :class:`DocumentInfo` is
returned by the store, so it lives in ``core``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from sift.core.types import Chunk, DocumentInfo


@runtime_checkable
class SupportsDocumentAdmin(Protocol):
    """The seam Dev B's ``/documents`` routes depend on — structural, so a fake can stand in."""

    async def list_documents(
        self,
        tenant: str,
        metadata: Mapping[str, str] | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DocumentInfo]:
        """List the tenant's ingested files, optionally narrowed to those with at least one
        chunk whose ``metadata`` matches every given key/value (additive param, default
        ``None`` — WP v0.2.0 T2's ``GET /v1/tools/documents``).

        ``limit``/``offset`` page the result *in the store* (default ``limit=None`` → no cap,
        preserving the original full-list behaviour). A paginating caller passes them so the DB
        materializes only the requested page instead of every document row (see
        :meth:`count_documents` for the matching total)."""
        ...

    async def count_documents(
        self, tenant: str, metadata: Mapping[str, str] | None = None
    ) -> int:
        """Total documents matching the same ``tenant``/``metadata`` filter as
        :meth:`list_documents`, ignoring pagination — the ``total`` a paged listing reports."""
        ...

    async def delete_document(self, source_hash: str, tenant: str) -> int: ...


@runtime_checkable
class SupportsChunkAccess(Protocol):
    """The seam ``GET /v1/tools/documents/{source_hash}/chunks`` depends on (WP v0.2.0 T2).

    Structural, like :class:`SupportsDocumentAdmin` — a store that hasn't grown this capability
    is detected via ``isinstance`` and the route degrades (empty list) rather than erroring.
    """

    async def get_chunks(self, source_hash: str, tenant: str) -> list[Chunk]:
        """Return every chunk of one ingested document, ordered by ``index`` ascending."""
        ...
