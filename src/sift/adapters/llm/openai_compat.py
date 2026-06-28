"""OpenAI-compatible chat adapter — (system, user) → recap text over async HTTP.

Implements the :class:`~sift.core.ports.Completer` port by POSTing the two turns to an
OpenAI-style ``{base_url}/chat/completions`` endpoint (``base_url`` already ends in ``/v1``)
and returning ``choices[0].message.content``. One ``httpx.AsyncClient`` per call (no shared
state), mirroring the embeddings adapter.
"""

from __future__ import annotations

import httpx


class OpenAICompatCompleter:
    """Completer backed by an OpenAI-compatible ``/chat/completions`` HTTP endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def complete(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self._max_tokens is not None:
            payload["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]
