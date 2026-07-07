"""In-memory test double for the :class:`~sift.core.ports.VectorStore` port.

Implements the per-tenant model-pin guard, the content-hash manifest, brute-force cosine
search, and tenant isolation — everything a pipeline needs to run end-to-end with no real
database.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from sift.core.errors import ModelPinMismatch, SiftError
from sift.core.types import Chunk, DocumentInfo, Hit, SearchFilters, Vector


class FakeVectorStore:
    """Per-tenant dicts give tenant isolation for free; rows key on (source_hash, index)."""

    def __init__(self) -> None:
        self._pins: dict[str, tuple[str, int]] = {}
        self._rows: dict[str, dict[tuple[str, int], Chunk]] = {}
        # Per-(tenant, source_hash) recency tokens, mirroring libSQL's ``files`` row. ``indexed_at``
        # is a monotonic counter (a document upserted later sorts as newer; deterministic, no
        # wall-clock); ``modified_at`` is the source file's real mtime carried on the Chunk.
        self._indexed_at: dict[str, dict[str, str]] = {}
        self._modified_at: dict[str, dict[str, str | None]] = {}
        self._seq = 0

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None:
        pinned = self._pins.get(tenant)
        if pinned is None:
            self._pins[tenant] = (model, dim)
            self._rows.setdefault(tenant, {})
            return
        if pinned != (model, dim):
            raise ModelPinMismatch(tenant=tenant, expected=pinned, actual=(model, dim))

    async def upsert(self, chunks: Sequence[Chunk], tenant: str) -> None:
        pin = self._pins.get(tenant)
        if pin is None:
            raise SiftError(f"tenant {tenant!r} not initialized; call ensure_ready() first")
        _model, dim = pin
        rows = self._rows.setdefault(tenant, {})
        stamps = self._indexed_at.setdefault(tenant, {})
        mtimes = self._modified_at.setdefault(tenant, {})
        for chunk in chunks:
            if chunk.vector is None:
                raise ValueError(f"chunk {chunk.source_hash}:{chunk.index} has no vector")
            if len(chunk.vector) != dim:
                raise ValueError(
                    f"vector dim {len(chunk.vector)} != pinned dim {dim} "
                    f"for chunk {chunk.source_hash}:{chunk.index}"
                )
            rows[(chunk.source_hash, chunk.index)] = chunk
            mtimes[chunk.source_hash] = chunk.modified_at
        # Stamp each document touched in this batch as more recent than anything before it.
        for source_hash in {chunk.source_hash for chunk in chunks}:
            self._seq += 1
            stamps[source_hash] = f"{self._seq:020d}"

    async def search(
        self, vector: Vector, k: int, tenant: str, filters: SearchFilters | None = None
    ) -> list[Hit]:
        rows = self._rows.get(tenant)
        if not rows:
            return []
        candidates = rows.values()
        if filters is not None:
            candidates = [chunk for chunk in candidates if _matches_filters(chunk, filters)]
        scored = [
            (_cosine(vector, chunk.vector), chunk)
            for chunk in candidates
            if chunk.vector is not None
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        stamps = self._indexed_at.get(tenant, {})
        mtimes = self._modified_at.get(tenant, {})
        return [
            Hit(
                text=chunk.text,
                score=score,
                source_path=chunk.source_path,
                page=chunk.page,
                source_hash=chunk.source_hash,
                index=chunk.index,
                modified_at=mtimes.get(chunk.source_hash),
                indexed_at=stamps.get(chunk.source_hash),
                metadata=chunk.metadata,
            )
            for score, chunk in scored[:k]
        ]

    async def known_hashes(self, tenant: str) -> set[str]:
        rows = self._rows.get(tenant)
        if not rows:
            return set()
        return {chunk.source_hash for chunk in rows.values()}

    def _matching_document_hashes(
        self, tenant: str, metadata: Mapping[str, str] | None
    ) -> tuple[list[str], dict[str, str], dict[str, int]]:
        """Sorted content-hashes matching ``tenant``/``metadata`` plus per-hash path/chunk-count —
        the shared core of ``list_documents`` and ``count_documents``."""
        rows = self._rows.get(tenant)
        if not rows:
            return [], {}, {}
        paths: dict[str, str] = {}
        counts: dict[str, int] = {}
        matched: set[str] = set()
        for chunk in rows.values():
            paths.setdefault(chunk.source_hash, chunk.source_path)
            counts[chunk.source_hash] = counts.get(chunk.source_hash, 0) + 1
            if metadata and _metadata_matches(chunk.metadata, metadata):
                matched.add(chunk.source_hash)
        hashes = matched if metadata else counts.keys()
        return sorted(hashes), paths, counts

    async def list_documents(
        self,
        tenant: str,
        metadata: Mapping[str, str] | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DocumentInfo]:
        hashes, paths, counts = self._matching_document_hashes(tenant, metadata)
        page = hashes[offset:] if limit is None else hashes[offset : offset + limit]
        stamps = self._indexed_at.get(tenant, {})
        mtimes = self._modified_at.get(tenant, {})
        return [
            DocumentInfo(
                source_path=paths[h],
                source_hash=h,
                chunks=counts[h],
                modified_at=mtimes.get(h),
                indexed_at=stamps.get(h),
            )
            for h in page
        ]

    async def count_documents(self, tenant: str, metadata: Mapping[str, str] | None = None) -> int:
        hashes, _paths, _counts = self._matching_document_hashes(tenant, metadata)
        return len(hashes)

    async def delete_document(self, source_hash: str, tenant: str) -> int:
        rows = self._rows.get(tenant)
        if not rows:
            return 0
        victims = [key for key in rows if key[0] == source_hash]
        for key in victims:
            del rows[key]
        return len(victims)

    async def get_chunks(self, source_hash: str, tenant: str) -> list[Chunk]:
        rows = self._rows.get(tenant)
        if not rows:
            return []
        chunks = [chunk for chunk in rows.values() if chunk.source_hash == source_hash]
        return sorted(chunks, key=lambda chunk: chunk.index)


def _metadata_matches(actual: dict[str, str] | None, wanted: Mapping[str, str]) -> bool:
    """True when ``actual`` has every ``wanted`` key with the exact given value."""
    if actual is None:
        return False
    return all(actual.get(key) == value for key, value in wanted.items())


def _matches_filters(chunk: Chunk, filters: SearchFilters) -> bool:
    """Mirrors ``LibSQLStore``'s SQL-side filter semantics (raw ISO-8601 string comparison)."""
    if filters.metadata and not _metadata_matches(chunk.metadata, filters.metadata):
        return False
    if filters.since is not None or filters.until is not None:
        if chunk.modified_at is None:
            return False
        if filters.since is not None and chunk.modified_at < filters.since:
            return False
        if filters.until is not None and chunk.modified_at > filters.until:
            return False
    return True


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
