"""The document-admin seam — list and delete ingested source files (README §3).

A capability :class:`typing.Protocol`, exactly like :class:`~sift.pipelines.ingest.SupportsIngest`:
Dev B's ``/documents`` routes depend on this structural seam, never on a concrete store, so a
store that implements it (the fake today, libSQL later) is picked up automatically and one that
doesn't degrades gracefully — the route reports it unsupported rather than failing. Ports/types
only (the dependency rule: ``pipelines`` never imports an adapter); :class:`DocumentInfo` is
returned by the store, so it lives in ``core``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sift.core.types import DocumentInfo


@runtime_checkable
class SupportsDocumentAdmin(Protocol):
    """The seam Dev B's ``/documents`` routes depend on — structural, so a fake can stand in."""

    async def list_documents(self, tenant: str) -> list[DocumentInfo]: ...

    async def delete_document(self, source_hash: str, tenant: str) -> int: ...
