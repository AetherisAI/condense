"""Thin ``httpx`` wrapper over the Sift ingest wire contract (bearer-auth).

Two calls back the agent's dedup-then-upload flow: :meth:`SiftClient.manifest` (the set of
content-hashes a tenant already has) and :meth:`SiftClient.ingest` (a multipart upload of
new files). This module imports only ``httpx`` + stdlib — never ``sift``.
"""

from __future__ import annotations

from typing import Any

import httpx


class SiftClient:
    """A bearer-authenticated client for the Sift ingest endpoints."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._c = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": "Bearer " + token},
        )

    def manifest(self, tenant: str) -> set[str]:
        """Return the set of content-hashes already ingested for ``tenant``."""
        r = self._c.get("/ingest/manifest", params={"tenant": tenant})
        r.raise_for_status()
        return set(r.json()["hashes"])

    def ingest(self, tenant: str, files: list[tuple[str, bytes]]) -> dict[str, Any]:
        """Upload ``(name, data)`` files as multipart field ``files``; return the JSON body."""
        r = self._c.post(
            "/ingest",
            params={"tenant": tenant},
            files=[("files", (name, data, "application/octet-stream")) for name, data in files],
        )
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._c.close()
