"""OpenAI-compatible embeddings adapter — text → vector over async HTTP.

Implements the :class:`~sift.core.ports.Embedder` port by POSTing to an OpenAI-style
``{base_url}/embeddings`` endpoint (``base_url`` already ends in ``/v1``). Each returned
``data[i].embedding`` is converted to an immutable :data:`~sift.core.types.Vector` tuple and
length-checked against the configured ``dim`` — a server answering with the wrong width fails
loudly here rather than corrupting a base. One ``httpx.AsyncClient`` per call (no shared state).

**429 retry (DECISIONS.md D34):** TEI (D30) hands out one concurrency permit *per input string*
on ``/v1/embeddings`` — a batch with more inputs than free permits gets an instant 429 "Model is
overloaded", which is retryable (not a real failure). A batch request is retried with a bounded,
fixed backoff (0.5s/2s/8s) on HTTP 429 only; any other status still fails immediately. This path
is unchanged by everything below.

**Poison-input isolation (DECISIONS.md D73):** a backend with a small physical batch (llama.cpp's
``n_ubatch``, a re-tokenizer that adds BOS/EOS, ...) can reject a single oversized input with a
non-429 error — and some backends (llama-server, observed live) cancel the WHOLE request's other
inputs too, not just the offending one. On a 4xx/5xx to a >1-input request, the batch is bisected
and each half retried recursively so one bad input never sacrifices its siblings. A batch that has
been bisected down to exactly one input and still fails gets a single truncate-the-tail-by-~10%
retry (a last-ditch shrink, not the proactive ``embed_max_input_tokens`` cap below); if that also
fails, :class:`~sift.core.errors.EmbedInputError` is raised naming the input's index (within the
``texts`` argument of that ``embed()`` call) and the backend's own error message — never a bare
``httpx`` status string. ``pipelines/ingest.py`` catches this to drop just that one chunk and keep
indexing a document's other, good chunks.

**Proactive per-input cap:** ``max_input_tokens`` (``Settings.embed_max_input_tokens``, 0 = off)
truncates an input BEFORE ever sending it, based on a cheap char-count estimate — defense in depth
alongside the reactive isolation above, not a replacement for it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import httpx

from sift.core.errors import EmbedInputError
from sift.core.types import Vector

logger = logging.getLogger(__name__)

# Fixed backoff between 429 retries — only the attempt *count* is a plausible per-deployment
# tuning knob (``embed_retry_attempts``); the delays themselves aren't worth another config key.
_RETRY_BACKOFF_S: tuple[float, ...] = (0.5, 2.0, 8.0)

# Reactive single-input shrink (D73): once bisection has isolated exactly one input and it still
# fails for a non-429 reason, truncate its tail by this fraction and retry exactly once before
# giving up. Character-based (no tokenizer access at this layer — see the module docstring).
_SHRINK_FRACTION = 0.10

# Cheap, dependency-free chars-per-token used by both the proactive cap and log messages. Not
# exact — real tokenization lives in ``adapters/chunking`` (bge-m3/tiktoken), which this module
# must never import (the dependency rule; ``tests/contract/test_layering.py``).
_CHARS_PER_TOKEN_ESTIMATE = 2


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
        max_input_tokens: int = 0,
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
        # Proactive per-input cap (D73) — 0 disables it. See ``config.py``'s
        # ``embed_max_input_tokens`` and the module docstring.
        self._max_input_tokens = max_input_tokens

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        items = [self._apply_cap(text) for text in texts]
        vectors: list[Vector] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(items), self._batch_size):
                batch = items[start : start + self._batch_size]
                vectors.extend(await self._embed_batch(client, batch, headers, start))
        return vectors

    def _apply_cap(self, text: str) -> str:
        """Truncate ``text`` if its ESTIMATED token count exceeds ``max_input_tokens`` (0 = no
        cap). Estimate-only — see the module docstring for why this can't be exact here."""
        if self._max_input_tokens <= 0:
            return text
        estimated = len(text) // _CHARS_PER_TOKEN_ESTIMATE
        if estimated <= self._max_input_tokens:
            return text
        keep_chars = max(self._max_input_tokens * _CHARS_PER_TOKEN_ESTIMATE, 1)
        truncated = text[:keep_chars]
        logger.warning(
            "embed input truncated: estimated ~%d tokens exceeds EMBED_MAX_INPUT_TOKENS=%d "
            "(kept %d of %d chars)",
            estimated,
            self._max_input_tokens,
            len(truncated),
            len(text),
        )
        return truncated

    async def _embed_batch(
        self,
        client: httpx.AsyncClient,
        batch: list[str],
        headers: dict[str, str],
        base_index: int,
    ) -> list[Vector]:
        """Embed one HTTP-sized batch, isolating a poison input via bisection (D73).

        On a 4xx/5xx to a >1-input batch, splits it in half and retries each half recursively —
        so one bad input never blocks its siblings, order-independent. A batch already down to a
        single input that still fails gets one truncate-and-retry attempt
        (:meth:`_embed_single_with_shrink`); if that also fails, the resulting
        :class:`~sift.core.errors.EmbedInputError` (naming ``base_index``, the input's absolute
        position in the original ``texts`` argument to :meth:`embed`) propagates up, discarding
        any already-computed sibling vectors from THIS SAME top-level batch — the caller
        (``pipelines/ingest.py``) is expected to drop that one input and retry the rest itself.

        A 429 (even on a single-input batch) is never bisected/shrunk — ``_post_with_429_retry``
        already retried it with the configured backoff, and re-raising it here unchanged keeps
        that existing path byte-identical.
        """
        payload = {"model": self._model, "input": batch}
        try:
            data = await self._post_with_429_retry(client, payload, headers)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                raise
            if len(batch) > 1:
                mid = len(batch) // 2
                left = await self._embed_batch(client, batch[:mid], headers, base_index)
                right = await self._embed_batch(client, batch[mid:], headers, base_index + mid)
                return left + right
            vector = await self._embed_single_with_shrink(
                client, batch[0], headers, base_index, exc
            )
            return [vector]
        return [self._to_vector(item["embedding"]) for item in data]

    async def _embed_single_with_shrink(
        self,
        client: httpx.AsyncClient,
        text: str,
        headers: dict[str, str],
        index: int,
        first_error: httpx.HTTPStatusError,
    ) -> Vector:
        """The last-ditch recovery for one input that failed alone: truncate its tail by
        ``_SHRINK_FRACTION`` and retry exactly once; raise :class:`EmbedInputError` if that also
        fails (D73)."""
        keep_chars = max(1, int(len(text) * (1 - _SHRINK_FRACTION)))
        shrunk = text[:keep_chars]
        logger.warning(
            "embed input %d rejected (%s); retrying once truncated to %d/%d chars",
            index,
            _extract_error_message(first_error.response),
            len(shrunk),
            len(text),
        )
        payload = {"model": self._model, "input": [shrunk]}
        try:
            data = await self._post_with_429_retry(client, payload, headers)
        except httpx.HTTPStatusError as exc:
            message = _extract_error_message(exc.response)
            raise EmbedInputError(index=index, message=message) from exc
        return self._to_vector(data[0]["embedding"])

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


def _extract_error_message(response: httpx.Response) -> str:
    """Best-effort extraction of a backend's own error message from a failed response — tries
    common shapes (``{"error": {"message": ...}}``, ``{"error": "..."}``, ``{"message": ...}``)
    before falling back to the raw response text, so a caught failure never surfaces as a bare
    ``httpx`` status string."""
    try:
        body: Any = response.json()
    except ValueError:
        return response.text.strip() or f"HTTP {response.status_code}"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        if isinstance(error, str):
            return error
        message = body.get("message")
        if isinstance(message, str):
            return message
    return response.text.strip() or f"HTTP {response.status_code}"
