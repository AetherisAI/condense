"""OpenAI-compatible embeddings adapter — text → vector over async HTTP.

Implements the :class:`~sift.core.ports.Embedder` port by POSTing to an OpenAI-style
``{base_url}/embeddings`` endpoint (``base_url`` already ends in ``/v1``). Each returned
``data[i].embedding`` is converted to an immutable :data:`~sift.core.types.Vector` tuple and
length-checked against the configured ``dim`` — a server answering with the wrong width fails
loudly here rather than corrupting a base. One ``httpx.AsyncClient`` per call (no shared state).
"""

from __future__ import annotations

from collections.abc import Sequence

import httpx

from sift.core.types import Vector


class OpenAICompatEmbedder:
    """Embedder backed by an OpenAI-compatible ``/embeddings`` HTTP endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        dim: int = 1024,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {"model": self._model, "input": list(texts)}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/embeddings", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()["data"]
        return [self._to_vector(item["embedding"]) for item in data]

    def _to_vector(self, embedding: Sequence[float]) -> Vector:
        vector = tuple(float(component) for component in embedding)
        if len(vector) != self._dim:
            raise ValueError(f"embedding dim {len(vector)} != configured dim {self._dim}")
        return vector
