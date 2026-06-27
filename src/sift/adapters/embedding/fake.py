"""Deterministic test double for the :class:`~sift.core.ports.Embedder` port.

Same text → same unit vector across processes and runs (seeded from ``hashlib``, never
the salted builtin ``hash()``). It is NOT semantic: only *identical* text scores cosine
≈ 1.0; distinct texts land in roughly random directions. That is enough to drive the
pipeline and exercise exact-match retrieval without a real embedding server.
"""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Sequence

from sift.core.types import Vector


class FakeEmbedder:
    """In-memory Embedder producing deterministic, unit-norm pseudo-embeddings."""

    def __init__(self, dim: int = 1024) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> Vector:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        raw = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]
        norm = math.sqrt(sum(component * component for component in raw)) or 1.0
        return tuple(component / norm for component in raw)
