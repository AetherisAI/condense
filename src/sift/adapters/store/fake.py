"""In-memory test double for the :class:`~sift.core.ports.VectorStore` port.

Implements the per-tenant model-pin guard, the content-hash manifest, brute-force cosine
search, and tenant isolation — everything a pipeline needs to run end-to-end with no real
database.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from sift.core.errors import ModelPinMismatch, SiftError
from sift.core.types import Chunk, Hit, Vector


class FakeVectorStore:
    """Per-tenant dicts give tenant isolation for free; rows key on (source_hash, index)."""

    def __init__(self) -> None:
        self._pins: dict[str, tuple[str, int]] = {}
        self._rows: dict[str, dict[tuple[str, int], Chunk]] = {}

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
        for chunk in chunks:
            if chunk.vector is None:
                raise ValueError(f"chunk {chunk.source_hash}:{chunk.index} has no vector")
            if len(chunk.vector) != dim:
                raise ValueError(
                    f"vector dim {len(chunk.vector)} != pinned dim {dim} "
                    f"for chunk {chunk.source_hash}:{chunk.index}"
                )
            rows[(chunk.source_hash, chunk.index)] = chunk

    async def search(self, vector: Vector, k: int, tenant: str) -> list[Hit]:
        rows = self._rows.get(tenant)
        if not rows:
            return []
        scored = [
            (_cosine(vector, chunk.vector), chunk)
            for chunk in rows.values()
            if chunk.vector is not None
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            Hit(
                text=chunk.text,
                score=score,
                source_path=chunk.source_path,
                page=chunk.page,
                source_hash=chunk.source_hash,
                index=chunk.index,
            )
            for score, chunk in scored[:k]
        ]

    async def known_hashes(self, tenant: str) -> set[str]:
        rows = self._rows.get(tenant)
        if not rows:
            return set()
        return {chunk.source_hash for chunk in rows.values()}


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
