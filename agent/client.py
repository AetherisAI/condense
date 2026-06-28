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

    def documents(self) -> tuple[bool, list[dict[str, Any]]]:
        """Return ``(supported, documents)`` for the token's tenant.

        ``documents`` is a list of ``{path, source_hash, chunks}``. ``supported`` is ``False``
        when the configured store can't enumerate documents (then the list is empty) — the
        agent treats that as "replace/delete unavailable" and falls back to add-only.
        """
        r = self._c.get("/documents")
        r.raise_for_status()
        body = r.json()
        return bool(body.get("supported", True)), list(body.get("documents", []))

    def delete_document(self, source_hash: str) -> int:
        """Delete one indexed document by its content hash; return the chunk count removed."""
        r = self._c.delete(f"/documents/{source_hash}")
        r.raise_for_status()
        return int(r.json()["deleted_chunks"])

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._c.close()
