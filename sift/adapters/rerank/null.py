"""Identity reranker — keeps vector-search order (RERANK_STRATEGY=none)."""
from __future__ import annotations

from ...core.types import Hit


class NullReranker:
    def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]:
        return list(candidates)
