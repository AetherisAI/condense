"""Cross-encoder reranker over TEI's ``/rerank`` — true query↔passage scoring via async HTTP.

Implements the :class:`~sift.core.ports.Reranker` port by POSTing ``{query, texts}`` to a
Text-Embeddings-Inference ``/rerank`` endpoint, which returns a bare list of ``{index, score}``
ordered by descending relevance. Each candidate :class:`~sift.core.types.Hit` is reordered to
match and re-scored with the cross-encoder score (via :func:`dataclasses.replace`). One
``httpx.AsyncClient`` per call (no shared state), mirroring the embeddings/chat adapters.
"""

from __future__ import annotations

from dataclasses import replace

import httpx

from sift.core.types import Hit


class CrossEncoderReranker:
    """Reranker backed by a TEI ``/rerank`` HTTP endpoint."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]:
        if not candidates:
            return []
        payload = {"query": query, "texts": [candidate.text for candidate in candidates]}
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{self._base_url}/rerank", json=payload)
            response.raise_for_status()
            ranked = response.json()
        return [replace(candidates[item["index"]], score=float(item["score"])) for item in ranked]
