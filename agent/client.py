"""Thin ``httpx`` wrapper over the Sift ingest wire contract (bearer-auth).

Two calls back the agent's dedup-then-upload flow: :meth:`SiftClient.manifest` (the set of
content-hashes a tenant already has) and :meth:`SiftClient.ingest` (a multipart upload of
new files). This module imports only ``httpx`` + stdlib — never ``sift``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

import httpx


class PartialIngestError(RuntimeError):
    """A later batch's upload failed after one or more earlier batches already landed.

    ``partial`` is the merged response body (same shape :meth:`SiftClient.ingest` normally
    returns) for every batch that succeeded *before* the failure — so a caller can credit that
    progress instead of discarding it wholesale (see DECISIONS.md D32 / A4). The triggering
    exception is available both as ``__cause__`` (via ``raise ... from exc``) and as ``.cause``.
    """

    def __init__(self, partial: dict[str, Any], cause: Exception) -> None:
        super().__init__(str(cause))
        self.partial = partial
        self.cause = cause


def _resolve(body: bytes | Callable[[], bytes]) -> bytes:
    """Read ``body`` now if it's a lazy loader — only the batch being built holds real bytes."""
    return body() if callable(body) else body


class SiftClient:
    """A bearer-authenticated client for the Sift ingest endpoints."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout: float = 600.0,
        transport: httpx.BaseTransport | None = None,
        batch_size: int = 10,
    ) -> None:
        self._batch_size = batch_size
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

    def ingest(
        self,
        tenant: str,
        files: Sequence[tuple[str, bytes | Callable[[], bytes]]],
        modified_at: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Upload ``(name, data)`` files as multipart field ``files`` in batches; merge the bodies.

        Files go out ``batch_size`` at a time, not as one request. A single giant POST of a whole
        folder (a) can exceed Starlette's 1000-file multipart cap and (b) makes the server hold
        every file + its chunks + vectors at once and embed for longer than the client timeout —
        so the agent abandons and retries while the server keeps working, piling up overlapping
        ingests until OOM (see DECISIONS.md D29). Small batches commit incrementally (content-hash
        dedup then skips them on any retry) and keep the server's per-request memory bounded.

        ``data`` may be raw ``bytes`` **or** a zero-arg loader (``Callable[[], bytes]``); a loader
        is only invoked while building the batch it belongs to, so at most one batch's worth of
        file bytes is ever resident at once (A3) — the caller (e.g. :func:`agent.sync.sync`) can
        hand over thousands of files' metadata without holding all their content in memory.

        ``modified_at`` is an optional ``{upload_name: iso8601}`` map of each file's last-modified
        time, split per batch and sent as a ``modified_at`` form field so the server can prefer the
        newest version.

        If a batch fails **after** at least one earlier batch already landed, raises
        :class:`PartialIngestError` carrying the merged results of those earlier batches instead
        of losing them outright (A4); a failure on the very first batch just propagates normally
        since there is nothing yet to credit. A 200 response whose body isn't valid JSON counts as
        a failure too — decoding happens inside the same protected section as the POST itself, so
        it can't silently discard an earlier batch's already-landed results either (D35).
        """
        merged: dict[str, Any] = {}
        for start in range(0, len(files), self._batch_size):
            chunk = files[start : start + self._batch_size]
            names = {name for name, _ in chunk}
            sub = {k: v for k, v in modified_at.items() if k in names} if modified_at else None
            data = {"modified_at": json.dumps(sub)} if sub else None
            try:
                r = self._c.post(
                    "/ingest",
                    params={"tenant": tenant},
                    data=data,
                    files=[
                        ("files", (name, _resolve(body), "application/octet-stream"))
                        for name, body in chunk
                    ],
                )
                r.raise_for_status()
                body = r.json()
            except Exception as exc:
                if merged:
                    raise PartialIngestError(merged, exc) from exc
                raise
            if not merged:
                merged = body  # adopt the server's response shape (tenant, …) from batch 1
            else:
                merged.setdefault("results", []).extend(body.get("results", []))
        return merged or {"results": []}

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
