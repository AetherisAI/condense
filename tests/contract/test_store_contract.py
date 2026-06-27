"""Contract tests for the VectorStore port, via FakeVectorStore."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore
from sift.core.errors import ModelPinMismatch
from sift.core.ports import VectorStore
from sift.core.types import Chunk

MODEL = "bge-m3"
TENANT = "default"


async def _embedded(embedder: FakeEmbedder, chunk: Chunk) -> Chunk:
    (vector,) = await embedder.embed([chunk.text])
    return replace(chunk, vector=vector)


def test_fake_store_satisfies_port() -> None:
    impl: VectorStore = FakeVectorStore()
    assert isinstance(impl, VectorStore)


async def test_ensure_ready_pins_then_accepts_same_pin(store: FakeVectorStore, dim: int) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    await store.ensure_ready(MODEL, dim, TENANT)  # idempotent — must not raise


async def test_ensure_ready_rejects_model_or_dim_mismatch(store: FakeVectorStore, dim: int) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    with pytest.raises(ModelPinMismatch):
        await store.ensure_ready("other-model", dim, TENANT)
    with pytest.raises(ModelPinMismatch):
        await store.ensure_ready(MODEL, dim + 1, TENANT)


async def test_upsert_then_search_returns_best_with_citation(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
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
    assert math.isclose(best.score, 1.0, rel_tol=1e-9)


async def test_search_honors_k(store: FakeVectorStore, embedder: FakeEmbedder, dim: int) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunks = [
        Chunk(text=f"doc {i}", source_path=f"{i}.md", page=1, source_hash=f"h{i}", index=0)
        for i in range(5)
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["doc 2"])
    assert len(await store.search(query, 3, TENANT)) == 3


async def test_tenant_isolation(store: FakeVectorStore, embedder: FakeEmbedder, dim: int) -> None:
    await store.ensure_ready(MODEL, dim, "tenant-a")
    chunk = Chunk(text="only in a", source_path="a.md", page=1, source_hash="ha", index=0)
    await store.upsert([await _embedded(embedder, chunk)], "tenant-a")

    await store.ensure_ready(MODEL, dim, "tenant-b")
    (query,) = await embedder.embed(["only in a"])
    assert await store.search(query, 5, "tenant-b") == []
    assert await store.known_hashes("tenant-b") == set()

    assert await store.known_hashes("tenant-a") == {"ha"}
