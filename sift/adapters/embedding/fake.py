"""Deterministic, offline fake embedder for tests — no network."""
from __future__ import annotations

import hashlib
import math

from ...core.types import EMBED_DIM, Vector


class FakeEmbedder:
    """Same text -> same unit vector of length `dim`; different text -> different vector."""

    def __init__(self, dim: int = EMBED_DIM) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[Vector]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> Vector:
        vals: list[float] = []
        counter = 0
        while len(vals) < self.dim:
            digest = hashlib.sha256(f"{text}:{counter}".encode()).digest()
            for i in range(0, len(digest), 4):
                if len(vals) >= self.dim:
                    break
                n = int.from_bytes(digest[i:i + 4], "big")
                vals.append((n / 2**32) * 2 - 1)      # [-1, 1)
            counter += 1
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]
