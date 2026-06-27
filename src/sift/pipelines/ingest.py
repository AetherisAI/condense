"""The ingest pipeline — parse → chunk → embed → upsert, with dedup and failure isolation.

Ports only (the dependency rule: ``pipelines`` never imports an adapter). It takes a *batch*
of ``(filename, bytes)`` (matching the multipart ``/ingest`` route) and returns one
:class:`IngestOutcome` per input file, in input order. The pin check happens once up front so a
:class:`~sift.core.errors.ModelPinMismatch` fails the whole batch fast (HTTP 409 in Dev B's
routes); any other per-file error is isolated so its siblings still index.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal, Protocol, runtime_checkable

from sift.core.errors import ModelPinMismatch
from sift.core.hashing import content_hash
from sift.core.ports import Chunker, Embedder, Parser, VectorStore
from sift.core.types import Chunk


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
        self, files: Sequence[tuple[str, bytes]], tenant: str
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

    async def ingest(self, files: Sequence[tuple[str, bytes]], tenant: str) -> list[IngestOutcome]:
        await self._store.ensure_ready(self._model, self._dim, tenant)
        known = set(await self._store.known_hashes(tenant))
        outcomes: list[IngestOutcome] = []
        for filename, data in files:
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
                vectors = await self._embedder.embed([c.text for c in chunks])
                embedded: list[Chunk] = [
                    replace(c, vector=v) for c, v in zip(chunks, vectors, strict=True)
                ]
                await self._store.upsert(embedded, tenant)
                known.add(digest)
                outcomes.append(
                    IngestOutcome(
                        path=filename,
                        status="indexed",
                        content_hash=digest,
                        chunks=len(chunks),
                    )
                )
            except ModelPinMismatch:
                raise
            except Exception as exc:
                outcomes.append(IngestOutcome(path=filename, status="failed", detail=str(exc)))
        return outcomes
