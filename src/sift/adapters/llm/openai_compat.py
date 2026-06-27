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
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    async def complete(self, system: str, user: str) -> str:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]
