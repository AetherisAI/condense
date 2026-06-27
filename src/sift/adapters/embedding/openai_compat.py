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

# Embed in batches so a large document (thousands of chunks) doesn't go out as one giant
# request — bounds memory/latency per call and stays under server batch limits. The timeout
# is generous because a CPU/Metal embedder can take well over httpx's 5s default on a batch.
_BATCH_SIZE = 64
_TIMEOUT = httpx.Timeout(120.0)


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
        items = list(texts)
        vectors: list[Vector] = []
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for start in range(0, len(items), _BATCH_SIZE):
                batch = items[start : start + _BATCH_SIZE]
                payload = {"model": self._model, "input": batch}
                response = await client.post(
                    f"{self._base_url}/embeddings", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()["data"]
                vectors.extend(self._to_vector(item["embedding"]) for item in data)
        return vectors

    def _to_vector(self, embedding: Sequence[float]) -> Vector:
        vector = tuple(float(component) for component in embedding)
        if len(vector) != self._dim:
            raise ValueError(f"embedding dim {len(vector)} != configured dim {self._dim}")
        return vector
