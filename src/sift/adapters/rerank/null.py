"""Identity reranker: keeps vector-search order so the search pipeline can go green
before the real TEI cross-encoder lands. Selected by ``RERANK_STRATEGY=none`` (README §7).
"""

from __future__ import annotations

from sift.core.types import Hit


class NullReranker:
    """Returns the candidates unchanged — a fresh list, no aliasing, no re-scoring."""

    async def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]:
        return list(candidates)
