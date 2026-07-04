"""OpenAI-compatible embeddings adapter — text → vector over async HTTP.

Implements the :class:`~sift.core.ports.Embedder` port by POSTing to an OpenAI-style
``{base_url}/embeddings`` endpoint (``base_url`` already ends in ``/v1``). Each returned
``data[i].embedding`` is converted to an immutable :data:`~sift.core.types.Vector` tuple and
length-checked against the configured ``dim`` — a server answering with the wrong width fails
loudly here rather than corrupting a base. One ``httpx.AsyncClient`` per call (no shared state).

**429 retry (DECISIONS.md D34):** TEI (D30) hands out one concurrency permit *per input string*
on ``/v1/embeddings`` — a batch with more inputs than free permits gets an instant 429 "Model is
overloaded", which is retryable (not a real failure). A batch request is retried with a bounded,
fixed backoff (0.5s/2s/8s) on HTTP 429 only; any other status still fails immediately.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import httpx

from sift.core.types import Vector

# Fixed backoff between 429 retries — only the attempt *count* is a plausible per-deployment
# tuning knob (``embed_retry_attempts``); the delays themselves aren't worth another config key.
_RETRY_BACKOFF_S: tuple[float, ...] = (0.5, 2.0, 8.0)


class OpenAICompatEmbedder:
    """Embedder backed by an OpenAI-compatible ``/embeddings`` HTTP endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        dim: int = 1024,
        *,
        batch_size: int = 64,
        timeout_s: float = 60.0,
        connect_timeout_s: float = 5.0,
        retry_attempts: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._dim = dim
        # Embed in batches so a large document (thousands of chunks) doesn't go out as one giant
        # request — bounds memory/latency per call and stays under server batch limits.
        self._batch_size = batch_size
        # Two independent, config-driven timeout phases: a short connect budget so an
        # unreachable/dead backend fails fast, a longer one for the rest of a slow (but
        # connected) call — see ``config.py``'s ``embed_timeout_s``/``embed_connect_timeout_s``.
        self._timeout = httpx.Timeout(timeout_s, connect=connect_timeout_s)
        # Total attempts (first try + retries) for a single batch's HTTP 429 — config-driven via
        # ``Settings.embed_retry_attempts``.
        self._retry_attempts = retry_attempts

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        items = list(texts)
        vectors: list[Vector] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(items), self._batch_size):
                batch = items[start : start + self._batch_size]
                payload = {"model": self._model, "input": batch}
                data = await self._post_with_429_retry(client, payload, headers)
                vectors.extend(self._to_vector(item["embedding"]) for item in data)
        return vectors

    async def _post_with_429_retry(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> list[dict[str, Any]]:
        """POST one batch, retrying only on HTTP 429 up to ``self._retry_attempts`` attempts."""
        for attempt in range(self._retry_attempts):
            response = await client.post(
                f"{self._base_url}/embeddings", json=payload, headers=headers
            )
            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                if attempt == self._retry_attempts - 1:
                    response.raise_for_status()
                await asyncio.sleep(_RETRY_BACKOFF_S[min(attempt, len(_RETRY_BACKOFF_S) - 1)])
                continue
            response.raise_for_status()
            return response.json()["data"]
        # Unreachable: the loop above always either returns or raises on its last attempt.
        raise AssertionError("unreachable: retry loop exited without returning or raising")

    def _to_vector(self, embedding: Sequence[float]) -> Vector:
        vector = tuple(float(component) for component in embedding)
        if len(vector) != self._dim:
            raise ValueError(f"embedding dim {len(vector)} != configured dim {self._dim}")
        return vector
