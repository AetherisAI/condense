"""In-memory fake VectorStore — brute-force cosine search. Tests only."""
from __future__ import annotations

import math

from ...core.types import Chunk, Hit, Vector


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class FakeVectorStore:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._model: str | None = None
        self._dim: int | None = None

    def ensure_ready(self, model: str, dim: int) -> None:
        self._model, self._dim = model, dim

    def upsert(self, chunks: list[Chunk]) -> None:
        self._chunks.extend(c for c in chunks if c.embedding is not None)

    def search(self, vector: Vector, k: int, tenant: str) -> list[Hit]:
        scored = [(_cosine(vector, c.embedding), c) for c in self._chunks
                  if c.tenant == tenant and c.embedding is not None]
        scored.sort(key=lambda s: s[0], reverse=True)
        return [Hit(id=c.id, text=c.text, path=c.path, page=c.page, score=score)
                for score, c in scored[:k]]

    def known_hashes(self, tenant: str) -> set[str]:
        return {c.content_hash for c in self._chunks if c.tenant == tenant}
