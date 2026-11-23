"""Cross-encoder reranker over a ``/rerank`` HTTP endpoint — true query↔passage scoring.

Implements the :class:`~sift.core.ports.Reranker` port by POSTing ``{query, texts}`` to a
``/rerank`` endpoint in Text-Embeddings-Inference's request shape, which returns a list of
``{index, score}`` ordered by descending relevance. Two servers speak it: TEI, and llama.cpp's
``llama-server --reranking`` (the desktop app's sidecar and the compose ``reranker`` service, both
serving ``bge-reranker-v2-m3``). Each candidate :class:`~sift.core.types.Hit` is reordered to
match and re-scored with the cross-encoder score (via :func:`dataclasses.replace`).

Scores: TEI sigmoids its scores unless asked for ``raw_scores``; llama-server ignores that flag
and always returns raw logits. The adapter asks for raw logits and applies the sigmoid itself,
so every backend reports the same 0..1 relevance.

Availability: a reranker that isn't listening at all (``httpx.ConnectError``: the desktop sidecar
not downloaded yet, or crashed) leaves the retrieval order in place with a warning instead of
failing the search; a reranker that answers with an error still raises.

One ``httpx.AsyncClient`` per call (no shared state), mirroring the embeddings/chat adapters, with
``RERANK_TIMEOUT_S`` as its budget: httpx's 5 s default is too short for a CPU cross-encoder
scoring up to ``RETRIEVE_K`` full chunks.

Score cache: reranking is the slowest step of a search (about 2 s on Apple-silicon Metal, 10 s or
more on CPU), and the same query often comes back. With a ``score_cache``, each (query, passage
text) pair's score is kept and only the pairs not seen yet are sent, or no request at all when
every pair is cached. That works because a cross-encoder scores each pair on its own, so a score
doesn't depend on which other passages came with it. The key is a hash of the query and the
passage's text, so an edited document gets new keys and can never be served a stale score. The
cache lives here rather than in a wrapper because only this adapter knows when its result is
the unreachable-reranker fallback, which must never be cached.
"""

from __future__ import annotations

import hashlib
import logging
import math
from collections.abc import Sequence
from dataclasses import replace

import httpx

from sift.adapters.cache.lru import LruCache
from sift.core.types import Hit

logger = logging.getLogger(__name__)


def _sigmoid(logit: float) -> float:
    # Split by sign so math.exp never overflows on large-magnitude logits.
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    exp = math.exp(logit)
    return exp / (1.0 + exp)


def _pair_key(query: str, text: str) -> bytes:
    """A 16-byte digest of one (query, passage) pair: the score cache's key, far smaller than the
    passage text itself."""
    return hashlib.blake2b(f"{query}\0{text}".encode(), digest_size=16).digest()


class CrossEncoderReranker:
    """Reranker backed by a TEI-shaped ``/rerank`` HTTP endpoint (TEI or llama-server)."""

    def __init__(
        self,
        base_url: str,
        timeout_s: float = 120.0,
        score_cache: LruCache[bytes, float] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._score_cache = score_cache

    async def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]:
        if not candidates:
            return []
        cache = self._score_cache
        keys: list[bytes] = []
        scores: dict[int, float] = {}  # candidate position -> relevance in 0..1
        if cache is not None:
            keys = [_pair_key(query, candidate.text) for candidate in candidates]
            for position, key in enumerate(keys):
                cached = cache.get(key)
                if cached is not None:
                    scores[position] = cached
        missing = [position for position in range(len(candidates)) if position not in scores]
        if missing:
            fetched = await self._score(query, [candidates[position].text for position in missing])
            if fetched is None:
                # Unreachable: keep the retrieval order, even when some scores were cached, so
                # the list is never ranked on two scales at once.
                return list(candidates)
            for item_index, score in fetched:
                position = missing[item_index]
                scores[position] = score
                if cache is not None:
                    cache.put(keys[position], score)
        # Best first; ties keep their retrieval order.
        order = sorted(scores, key=lambda position: (-scores[position], position))
        return [replace(candidates[position], score=scores[position]) for position in order]

    async def _score(self, query: str, texts: Sequence[str]) -> list[tuple[int, float]] | None:
        """``(index into texts, relevance in 0..1)`` for each text the server scored, or ``None``
        when nothing is listening."""
        payload = {"query": query, "texts": list(texts), "raw_scores": True}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                response = await client.post(f"{self._base_url}/rerank", json=payload)
        except httpx.ConnectError as exc:
            logger.warning(
                "reranker unreachable at %s (%s); keeping the retrieval order",
                self._base_url,
                exc,
            )
            return None
        response.raise_for_status()
        return [(item["index"], _sigmoid(float(item["score"]))) for item in response.json()]
