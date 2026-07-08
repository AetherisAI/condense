"""The ingest pipeline — parse → chunk → embed → upsert, with dedup and failure isolation.

Ports only (the dependency rule: ``pipelines`` never imports an adapter). It takes a *batch*
of ``(filename, bytes)`` — a plain list (JSON ingest, tests) or a lazy async stream (the
multipart ``/ingest`` route, so peak RAM stays at roughly one file, not the sum of the batch;
see :data:`IngestFiles`/:func:`stream_files`) — and returns one :class:`IngestOutcome` per
input file, in input order. The pin check happens once up front so a
:class:`~sift.core.errors.ModelPinMismatch` fails the whole batch fast (HTTP 409 in Dev B's
routes); any other per-file error is isolated so its siblings still index.

**Per-chunk embed failure isolation (DECISIONS.md D73):** a conforming :class:`~sift.core.ports.
Embedder` may raise :class:`~sift.core.errors.EmbedInputError` for one rejected input (an
oversized chunk a backend's physical batch can't take, after the adapter's own bisection/shrink
already tried to salvage it) — see :meth:`IngestPipeline._embed_isolating_bad_inputs`. That one
chunk is dropped and the rest of the document is still indexed (``status="indexed"`` with a
``detail`` noting how many chunks were skipped and why); only when EVERY chunk is rejected does
the file become ``status="failed"``, with the embedder's own message as ``detail`` — never a bare
``httpx`` status string. Any other embed exception (a network error, an exhausted 429, ...) is
unrelated to a specific input and still fails the whole file via the existing outer
``except Exception``, unchanged.
"""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Literal, Protocol, runtime_checkable

from sift.core.errors import EmbedInputError, ModelPinMismatch
from sift.core.hashing import content_hash
from sift.core.ports import Chunker, Embedder, Parser, VectorStore
from sift.core.types import Chunk, Vector

# A source of ``(filename, bytes)`` files. Accepts a lazy **async** stream — the ``/ingest`` route
# passes an async generator that reads one UploadFile at a time, so only a single file's bytes are
# resident (bounded peak RAM, no spike on a large multi-file upload) — or any plain iterable (a
# list, in tests). Normalized to one async stream by :func:`stream_files`.
IngestFiles = AsyncIterable[tuple[str, bytes]] | Iterable[tuple[str, bytes]]


async def stream_files(files: IngestFiles) -> AsyncIterator[tuple[str, bytes]]:
    """Yield ``(filename, bytes)`` from either an async or a sync source as one async stream."""
    if isinstance(files, AsyncIterable):
        async for item in files:
            yield item
    else:
        for item in files:
            yield item


@dataclass(frozen=True, slots=True, kw_only=True)
class IngestOutcome:
    """The per-file result of an ingest run (mapped to the API schema by Dev B's routes)."""

    path: str
    status: Literal["indexed", "skipped_dedup", "failed"]
    content_hash: str | None = None
    chunks: int | None = None
    detail: str | None = None


@runtime_checkable
class SupportsIngest(Protocol):
    """The seam Dev B's ``/ingest`` route depends on — structural, so a fake can stand in."""

    async def ingest(
        self,
        files: IngestFiles,
        tenant: str,
        modified_at: Mapping[str, str] | None = None,
        metadata: Mapping[str, dict[str, str]] | None = None,
    ) -> list[IngestOutcome]: ...


class IngestPipeline:
    """Wires the four ports together; pins ``(model, dim)`` per tenant on first use."""

    def __init__(
        self,
        parser: Parser,
        chunker: Chunker,
        embedder: Embedder,
        store: VectorStore,
        *,
        model: str,
        dim: int,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._store = store
        self._model = model
        self._dim = dim

    async def ingest(
        self,
        files: IngestFiles,
        tenant: str,
        modified_at: Mapping[str, str] | None = None,
        metadata: Mapping[str, dict[str, str]] | None = None,
    ) -> list[IngestOutcome]:
        await self._store.ensure_ready(self._model, self._dim, tenant)
        known = set(await self._store.known_hashes(tenant))
        mtimes = modified_at or {}
        file_metadata = metadata or {}
        outcomes: list[IngestOutcome] = []
        async for filename, data in stream_files(files):
            try:
                digest = content_hash(data)
                if digest in known:
                    outcomes.append(
                        IngestOutcome(path=filename, status="skipped_dedup", content_hash=digest)
                    )
                    continue
                doc = await self._parser.parse(data, filename)
                chunks = await self._chunker.chunk(doc)
                if not chunks:
                    known.add(digest)
                    outcomes.append(
                        IngestOutcome(
                            path=filename,
                            status="indexed",
                            content_hash=digest,
                            chunks=0,
                            detail="no extractable text",
                        )
                    )
                    continue
                surviving, vectors, skip_details = await self._embed_isolating_bad_inputs(chunks)
                if vectors is None:
                    # Every chunk was rejected — nothing left of this file to index.
                    outcomes.append(
                        IngestOutcome(
                            path=filename,
                            status="failed",
                            content_hash=digest,
                            detail=f"all {len(chunks)} chunks failed to embed: {skip_details[-1]}",
                        )
                    )
                    continue
                file_mtime = mtimes.get(filename)
                file_meta = file_metadata.get(filename)
                embedded: list[Chunk] = [
                    replace(c, vector=v, modified_at=file_mtime, metadata=file_meta)
                    for c, v in zip(surviving, vectors, strict=True)
                ]
                await self._store.upsert(embedded, tenant)
                known.add(digest)
                detail = (
                    f"{len(skip_details)} chunks skipped: " + "; ".join(skip_details)
                    if skip_details
                    else None
                )
                outcomes.append(
                    IngestOutcome(
                        path=filename,
                        status="indexed",
                        content_hash=digest,
                        chunks=len(surviving),
                        detail=detail,
                    )
                )
            except ModelPinMismatch:
                raise
            except Exception as exc:
                outcomes.append(IngestOutcome(path=filename, status="failed", detail=str(exc)))
        return outcomes

    async def _embed_isolating_bad_inputs(
        self, chunks: list[Chunk]
    ) -> tuple[list[Chunk], list[Vector] | None, list[str]]:
        """Embed ``chunks``, dropping any the embedder rejects one at a time instead of failing
        the whole document for a single bad chunk (D73).

        On :class:`~sift.core.errors.EmbedInputError`, the offending chunk — identified by the
        error's ``index`` into the CURRENT ``remaining`` list, which is always freshly re-indexed
        on every attempt — is dropped and the rest are re-embedded from scratch; this repeats
        until either every remaining chunk embeds successfully or none are left. Returns
        ``(surviving_chunks, vectors, skip_details)``; ``vectors is None`` iff every chunk was
        rejected (``skip_details`` still holds every reason, in encounter order — the caller uses
        the last one as the file's real failure detail). Any OTHER exception (a network error, an
        exhausted 429, a dimension mismatch, ...) is not a per-input problem and propagates
        unchanged, so the caller's whole-file ``except Exception`` still marks the file failed
        exactly as before this method existed.
        """
        remaining = list(chunks)
        skip_details: list[str] = []
        while remaining:
            try:
                vectors = await self._embedder.embed([c.text for c in remaining])
            except EmbedInputError as exc:
                bad_chunk = remaining.pop(exc.index)
                skip_details.append(f"chunk {bad_chunk.index}: {exc.message}")
                continue
            return remaining, vectors, skip_details
        return remaining, None, skip_details
