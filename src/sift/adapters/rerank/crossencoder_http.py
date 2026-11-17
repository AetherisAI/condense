"""Cross-encoder reranker over a ``/rerank`` HTTP endpoint — true query↔passage scoring.

Implements the :class:`~sift.core.ports.Reranker` port by POSTing ``{query, texts}`` to a
``/rerank`` endpoint in Text-Embeddings-Inference's request shape, which returns a list of
``{index, score}`` ordered by descending relevance. Two servers speak it: TEI, and llama.cpp's
``llama-server --reranking`` (the desktop app's sidecar and the compose ``reranker`` service, both
serving ``bge-reranker-v2-m3``; D88). Each candidate :class:`~sift.core.types.Hit` is reordered to
match and re-scored with the cross-encoder score (via :func:`dataclasses.replace`).

Scores: TEI sigmoids its scores unless asked for ``raw_scores``; llama-server ignores that flag
and always returns raw logits. The adapter asks for raw logits and applies the sigmoid itself,
so every backend reports the same 0..1 relevance (D88).

Availability: a reranker that isn't listening at all (``httpx.ConnectError``: the desktop sidecar
not downloaded yet, or crashed) leaves the retrieval order in place with a warning instead of
failing the search; a reranker that answers with an error still raises (D88).

One ``httpx.AsyncClient`` per call (no shared state), mirroring the embeddings/chat adapters, with
``RERANK_TIMEOUT_S`` as its budget: httpx's 5 s default is too short for a CPU cross-encoder
scoring up to ``RETRIEVE_K`` full chunks (D83).
"""

from __future__ import annotations

import logging
import math
from dataclasses import replace

import httpx

from sift.core.types import Hit

logger = logging.getLogger(__name__)


def _sigmoid(logit: float) -> float:
    # Split by sign so math.exp never overflows on large-magnitude logits.
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp = math.exp(logit)
    return exp / (1.0 + exp)


class CrossEncoderReranker:
    """Reranker backed by a TEI-shaped ``/rerank`` HTTP endpoint (TEI or llama-server)."""

    def __init__(self, base_url: str, timeout_s: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    async def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]:
        if not candidates:
            return []
        payload = {
            "query": query,
            "texts": [candidate.text for candidate in candidates],
            "raw_scores": True,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.post(f"{self._base_url}/rerank", json=payload)
        except httpx.ConnectError as exc:
            logger.warning(
                "reranker unreachable at %s (%s); keeping the retrieval order",
                self._base_url,
                exc,
            )
            return list(candidates)
        response.raise_for_status()
        ranked = response.json()
        return [
            replace(candidates[item["index"]], score=_sigmoid(float(item["score"])))
            for item in ranked
        ]
