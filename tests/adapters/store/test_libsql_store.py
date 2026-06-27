"""Tests for :class:`~sift.adapters.store.libsql.LibSQLStore` (parity with FakeVectorStore).

Each test runs against a fresh temp-file libSQL DB (``tmp_path``) and tears the store down via
``aclose()``. ``pytest-asyncio`` auto mode runs the ``async def`` tests. Vectors round-trip through
``F32_BLOB``, so exact-match score asserts use ``rel_tol=1e-4`` (looser than the fake's ``1e-9``).
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator
from dataclasses import replace

import pytest

libsql = pytest.importorskip("libsql")

from sift.adapters.embedding.fake import FakeEmbedder  # noqa: E402
from sift.adapters.store.libsql import LibSQLStore  # noqa: E402
from sift.core.errors import ModelPinMismatch, SiftError  # noqa: E402
from sift.core.ports import VectorStore  # noqa: E402
from sift.core.types import Chunk  # noqa: E402

MODEL = "bge-m3"
DIM = 8
TENANT = "default"


@pytest.fixture
async def store(tmp_path) -> AsyncIterator[LibSQLStore]:
    impl = LibSQLStore(str(tmp_path / "sift.db"))
    try:
        yield impl
    finally:
        await impl.aclose()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder(dim=DIM)


async def _embedded(embedder: FakeEmbedder, chunk: Chunk) -> Chunk:
    (vector,) = await embedder.embed([chunk.text])
    return replace(chunk, vector=vector)


async def test_satisfies_vector_store_port(store: LibSQLStore) -> None:
    assert isinstance(store, VectorStore)


async def test_ensure_ready_pins_then_accepts_same_pin(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.ensure_ready(MODEL, DIM, TENANT)  # idempotent — must not raise
    assert await store.known_hashes(TENANT) == set()


async def test_ensure_ready_rejects_model_or_dim_mismatch(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    with pytest.raises(ModelPinMismatch):
        await store.ensure_ready("other-model", DIM, TENANT)
    with pytest.raises(ModelPinMismatch):
        await store.ensure_ready(MODEL, DIM + 1, TENANT)


async def test_upsert_then_search_returns_best_with_citation(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(text="the sky is blue", source_path="a.md", page=1, source_hash="h1", index=0),
        Chunk(text="grass is green", source_path="b.md", page=2, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["the sky is blue"])
    hits = await store.search(query, 5, TENANT)

    assert hits
    best = hits[0]
    assert best.source_path == "a.md"
    assert best.page == 1
    assert best.text == "the sky is blue"
    assert best.source_hash == "h1"
    assert best.index == 0
    assert math.isclose(best.score, 1.0, rel_tol=1e-4)


async def test_search_honors_k(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(text=f"doc {i}", source_path=f"{i}.md", page=1, source_hash=f"h{i}", index=0)
        for i in range(5)
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["doc 2"])
    assert len(await store.search(query, 3, TENANT)) == 3


async def test_search_empty_when_no_rows(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    (query,) = await embedder.embed(["nothing here"])
    assert await store.search(query, 5, TENANT) == []


async def test_tenant_isolation(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, "tenant-a")
    chunk = Chunk(text="only in a", source_path="a.md", page=1, source_hash="ha", index=0)
    await store.upsert([await _embedded(embedder, chunk)], "tenant-a")

    await store.ensure_ready(MODEL, DIM, "tenant-b")
    (query,) = await embedder.embed(["only in a"])
    assert await store.search(query, 5, "tenant-b") == []
    assert await store.known_hashes("tenant-b") == set()

    assert await store.known_hashes("tenant-a") == {"ha"}


async def test_known_hashes_returns_ingested_hash(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="hello", source_path="x.md", page=1, source_hash="hx", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)
    assert await store.known_hashes(TENANT) == {"hx"}


async def test_idempotent_reupsert_keeps_row_count_and_updates_text(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    original = Chunk(text="v1", source_path="a.md", page=1, source_hash="h1", index=0)
    await store.upsert([await _embedded(embedder, original)], TENANT)
    await store.upsert([await _embedded(embedder, original)], TENANT)  # identical re-upsert

    (query,) = await embedder.embed(["v1"])
    assert len(await store.search(query, 100, TENANT)) == 1  # row count stable

    updated = replace(original, text="v2")
    await store.upsert([await _embedded(embedder, updated)], TENANT)

    hits = await store.search(query, 100, TENANT)
    assert len(hits) == 1  # same (source_hash, index) key — no new row
    assert hits[0].text == "v2"  # changed text persisted


async def test_upsert_before_ensure_ready_raises_sift_error(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)
    with pytest.raises(SiftError):
        await store.upsert([await _embedded(embedder, chunk)], TENANT)


async def test_upsert_none_vector_raises_value_error(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)  # vector None
    with pytest.raises(ValueError):
        await store.upsert([chunk], TENANT)


async def test_upsert_wrong_dim_vector_raises_value_error(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    wrong = FakeEmbedder(dim=DIM + 1)
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)
    with pytest.raises(ValueError):
        await store.upsert([await _embedded(wrong, chunk)], TENANT)
