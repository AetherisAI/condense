"""The query-embedding cache: a decorator over any :class:`~sift.core.ports.Embedder`.

Embedding a query is an HTTP round trip (about 100–150 ms with bge-m3 on Ollama), and the same
query often comes back: a Find run again, Ask's agent searching for the same words twice, a
question asked in Find and then in Ask. The key is the text itself. The wrapped embedder's model
and prefix never change while it lives (a settings change builds a new container, and with it a
new cache), so a cached vector is always the one the embedder would return.

Vectors are stored as ``array("d")``, 8 bytes per component instead of the ~32 that a tuple of
Python floats takes, so 1,024 cached 1024-dim queries hold about 8 MB. A double holds a Python
float exactly, so nothing is lost.

``factory.py`` wraps only the query embedder: ingested chunks are almost all distinct, so caching
them would only use RAM.
"""

from __future__ import annotations

from array import array
from collections.abc import Sequence

from sift.adapters.cache.lru import LruCache
from sift.core.ports import Embedder
from sift.core.types import Vector


class CachingEmbedder:
    """Serves repeated texts from its cache and sends only the new ones to ``inner``."""

    def __init__(self, inner: Embedder, max_entries: int) -> None:
        self._inner = inner
        self._cache: LruCache[str, array[float]] = LruCache(max_entries)

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        distinct = list(dict.fromkeys(texts))
        vectors: dict[str, Vector] = {}
        for text in distinct:
            cached = self._cache.get(text)
            if cached is not None:
                vectors[text] = tuple(cached)
        missing = [text for text in distinct if text not in vectors]
        if missing:
            # A failure propagates before anything is stored, so the next call retries.
            fresh = await self._inner.embed(missing)
            for text, vector in zip(missing, fresh, strict=True):
                self._cache.put(text, array("d", vector))
                vectors[text] = vector
        return [vectors[text] for text in texts]
