"""Unit tests for :class:`~sift.pipelines.ingest.IngestPipeline` (fakes only, offline).

Drives the pipeline through ``FakeEmbedder`` + ``FakeVectorStore`` plus tiny in-test
``FakeParser``/``FakeChunker`` doubles, covering the indexed / skipped_dedup / failed paths,
intra-batch dedup, per-file failure isolation, fatal pin mismatch, empty text, and the
one-embed-call-per-doc / one-ensure_ready-call invariants.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore
from sift.core.errors import ModelPinMismatch
from sift.core.hashing import content_hash
from sift.core.types import Chunk, Document, Page, Vector
from sift.pipelines.ingest import IngestOutcome, IngestPipeline, SupportsIngest

MODEL = "bge-m3"
DIM = 16
TENANT = "default"


class FakeParser:
    """Bytes → a single-page Document; raises for filenames in ``fail_on``."""

    def __init__(self, fail_on: set[str] | None = None) -> None:
        self._fail_on = fail_on or set()

    async def parse(self, data: bytes, filename: str) -> Document:
        if filename in self._fail_on:
            raise RuntimeError(f"cannot parse {filename}")
        return Document(
            path=filename,
            content_hash=content_hash(data),
            pages=(Page(number=1, text=data.decode("utf-8")),),
        )


class FakeChunker:
    """One un-embedded Chunk per non-blank line; empty/blank text → no chunks."""

    async def chunk(self, doc: Document) -> list[Chunk]:
        text = "\n".join(page.text for page in doc.pages)
        lines = [line for line in text.splitlines() if line.strip()]
        return [
            Chunk(
                text=line,
                source_path=doc.path,
                page=1,
                source_hash=doc.content_hash,
                index=i,
                vector=None,
            )
            for i, line in enumerate(lines)
        ]


class CountingEmbedder:
    """Wraps FakeEmbedder to count how many times ``embed`` is invoked."""

    def __init__(self, inner: FakeEmbedder) -> None:
        self._inner = inner
        self.calls = 0

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        self.calls += 1
        return await self._inner.embed(texts)


class SpyStore:
    """Delegates to FakeVectorStore while counting ``ensure_ready`` calls."""

    def __init__(self) -> None:
        self.inner = FakeVectorStore()
        self.ensure_ready_calls = 0

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None:
        self.ensure_ready_calls += 1
        await self.inner.ensure_ready(model, dim, tenant)

    async def upsert(self, chunks: Sequence[Chunk], tenant: str) -> None:
        await self.inner.upsert(chunks, tenant)

    async def search(self, vector: Vector, k: int, tenant: str) -> list:
        return await self.inner.search(vector, k, tenant)

    async def known_hashes(self, tenant: str) -> set[str]:
        return await self.inner.known_hashes(tenant)


def _pipeline(
    store: object,
    embedder: object,
    *,
    parser: FakeParser | None = None,
    chunker: FakeChunker | None = None,
) -> IngestPipeline:
    return IngestPipeline(
        parser or FakeParser(),
        chunker or FakeChunker(),
        embedder,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        model=MODEL,
        dim=DIM,
    )


def test_pipeline_satisfies_seam() -> None:
    pipeline = _pipeline(FakeVectorStore(), FakeEmbedder(dim=DIM))
    assert isinstance(pipeline, SupportsIngest)


async def test_new_file_indexed_then_searchable() -> None:
    store = FakeVectorStore()
    embedder = FakeEmbedder(dim=DIM)
    pipeline = _pipeline(store, embedder)
    data = b"alpha beta\ngamma delta"

    outcomes = await pipeline.ingest([("doc.md", data)], TENANT)

    assert len(outcomes) == 1
    out = outcomes[0]
    assert isinstance(out, IngestOutcome)
    assert out.status == "indexed"
    assert out.path == "doc.md"
    assert out.content_hash == content_hash(data)
    assert out.chunks == 2

    (query,) = await embedder.embed(["alpha beta"])
    hits = await store.search(query, 5, TENANT)
    assert hits
    assert hits[0].text == "alpha beta"
    assert hits[0].source_path == "doc.md"
    assert math.isclose(hits[0].score, 1.0, rel_tol=1e-9)


async def test_dedup_skip_when_hash_already_in_store() -> None:
    store = FakeVectorStore()
    embedder = FakeEmbedder(dim=DIM)
    data = b"hello world"
    digest = content_hash(data)

    await store.ensure_ready(MODEL, DIM, TENANT)
    (vector,) = await embedder.embed(["hello world"])
    await store.upsert(
        [
            Chunk(
                text="hello world",
                source_path="seed.md",
                page=1,
                source_hash=digest,
                index=0,
                vector=vector,
            )
        ],
        TENANT,
    )

    pipeline = _pipeline(store, embedder)
    outcomes = await pipeline.ingest([("hello.md", data)], TENANT)

    assert len(outcomes) == 1
    assert outcomes[0].status == "skipped_dedup"
    assert outcomes[0].content_hash == digest
    assert outcomes[0].chunks is None


async def test_intra_batch_dedup_skips_second_identical() -> None:
    pipeline = _pipeline(FakeVectorStore(), FakeEmbedder(dim=DIM))
    data = b"repeat me"

    outcomes = await pipeline.ingest([("first.md", data), ("second.md", data)], TENANT)

    assert [o.status for o in outcomes] == ["indexed", "skipped_dedup"]
    assert outcomes[0].path == "first.md"
    assert outcomes[1].path == "second.md"
    assert outcomes[1].content_hash == content_hash(data)


async def test_per_file_failure_is_isolated() -> None:
    parser = FakeParser(fail_on={"bad.md"})
    pipeline = _pipeline(FakeVectorStore(), FakeEmbedder(dim=DIM), parser=parser)
    files = [("good1.md", b"one"), ("bad.md", b"two"), ("good2.md", b"three")]

    outcomes = await pipeline.ingest(files, TENANT)

    assert [o.path for o in outcomes] == ["good1.md", "bad.md", "good2.md"]
    assert [o.status for o in outcomes] == ["indexed", "failed", "indexed"]
    assert outcomes[1].detail is not None
    assert "bad.md" in outcomes[1].detail


async def test_model_pin_mismatch_is_fatal() -> None:
    store = FakeVectorStore()
    await store.ensure_ready("other-model", DIM, TENANT)
    pipeline = _pipeline(store, FakeEmbedder(dim=DIM))

    with pytest.raises(ModelPinMismatch):
        await pipeline.ingest([("x.md", b"some data")], TENANT)


async def test_empty_text_indexed_with_zero_chunks() -> None:
    store = FakeVectorStore()
    embedder = FakeEmbedder(dim=DIM)
    pipeline = _pipeline(store, embedder)
    data = b""

    outcomes = await pipeline.ingest([("empty.md", data)], TENANT)

    assert len(outcomes) == 1
    out = outcomes[0]
    assert out.status == "indexed"
    assert out.chunks == 0
    assert out.detail == "no extractable text"
    assert out.content_hash == content_hash(data)
    # Nothing embeddable was stored.
    assert await store.known_hashes(TENANT) == set()


async def test_embed_called_once_per_indexed_doc() -> None:
    counting = CountingEmbedder(FakeEmbedder(dim=DIM))
    pipeline = _pipeline(FakeVectorStore(), counting)
    files = [
        ("a.md", b"alpha"),  # indexed -> embed
        ("b.md", b"beta"),  # indexed -> embed
        ("a-dup.md", b"alpha"),  # intra-batch dedup -> no embed
        ("empty.md", b""),  # indexed, 0 chunks -> no embed
    ]

    outcomes = await pipeline.ingest(files, TENANT)

    assert [o.status for o in outcomes] == [
        "indexed",
        "indexed",
        "skipped_dedup",
        "indexed",
    ]
    assert counting.calls == 2


async def test_ensure_ready_called_once_per_batch() -> None:
    spy = SpyStore()
    pipeline = _pipeline(spy, FakeEmbedder(dim=DIM))
    files = [("a.md", b"one"), ("b.md", b"two"), ("c.md", b"three")]

    await pipeline.ingest(files, TENANT)

    assert spy.ensure_ready_calls == 1


async def test_ingest_streams_files_one_at_a_time() -> None:
    """Peak memory guard: the pipeline pulls files lazily (one in flight), it must NOT drain the
    whole source up front. The route passes an async generator over UploadFiles so only one file's
    bytes are resident at a time; buffering them all is the RAM-spike regression this locks out.
    """
    pipeline = _pipeline(FakeVectorStore(), FakeEmbedder(dim=DIM))

    live = 0
    max_live = 0

    async def source():
        nonlocal live, max_live
        for i in range(5):
            live += 1  # this file's bytes become resident
            max_live = max(max_live, live)
            yield (f"f{i}.md", f"line {i}".encode())
            live -= 1  # resumed only after the pipeline finished with the previous file

    outcomes = await pipeline.ingest(source(), TENANT)

    assert [o.status for o in outcomes] == ["indexed"] * 5
    assert max_live == 1  # never more than one file resident; == 5 would mean it buffered them all
