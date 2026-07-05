"""Contract tests for the VectorStore port, via FakeVectorStore."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore
from sift.core.errors import ModelPinMismatch
from sift.core.ports import VectorStore
from sift.core.types import Chunk, SearchFilters

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


async def test_search_round_trips_metadata(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    tagged = Chunk(
        text="tagged passage",
        source_path="m.md",
        page=1,
        source_hash="hm",
        index=0,
        metadata={"author": "quentin", "kind": "note"},
    )
    untagged = Chunk(text="no tags here", source_path="n.md", page=1, source_hash="hn", index=0)
    await store.upsert(
        [await _embedded(embedder, tagged), await _embedded(embedder, untagged)], TENANT
    )

    (tagged_query,) = await embedder.embed(["tagged passage"])
    (tagged_hit,) = await store.search(tagged_query, 1, TENANT)
    assert tagged_hit.metadata == {"author": "quentin", "kind": "note"}

    (untagged_query,) = await embedder.embed(["no tags here"])
    (untagged_hit,) = await store.search(untagged_query, 1, TENANT)
    assert untagged_hit.metadata is None


async def test_search_honors_k(store: FakeVectorStore, embedder: FakeEmbedder, dim: int) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunks = [
        Chunk(text=f"doc {i}", source_path=f"{i}.md", page=1, source_hash=f"h{i}", index=0)
        for i in range(5)
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["doc 2"])
    assert len(await store.search(query, 3, TENANT)) == 3


async def test_search_metadata_filter_narrows_before_k(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunks = [
        Chunk(
            text="alpha one",
            source_path="a.md",
            page=1,
            source_hash="h1",
            index=0,
            metadata={"project": "condense"},
        ),
        Chunk(
            text="alpha two",
            source_path="b.md",
            page=1,
            source_hash="h2",
            index=0,
            metadata={"project": "other"},
        ),
        Chunk(text="alpha three", source_path="c.md", page=1, source_hash="h3", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["alpha"])
    hits = await store.search(query, 10, TENANT, SearchFilters(metadata={"project": "condense"}))

    assert [hit.source_path for hit in hits] == ["a.md"]


async def test_search_since_until_filter_narrows_by_modified_at(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunks = [
        Chunk(
            text="beta old",
            source_path="old.md",
            page=1,
            source_hash="ho",
            index=0,
            modified_at="2026-01-01T00:00:00+00:00",
        ),
        Chunk(
            text="beta new",
            source_path="new.md",
            page=1,
            source_hash="hn",
            index=0,
            modified_at="2026-06-01T00:00:00+00:00",
        ),
        Chunk(text="beta undated", source_path="u.md", page=1, source_hash="hu", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["beta"])
    hits = await store.search(query, 10, TENANT, SearchFilters(since="2026-03-01"))

    assert [hit.source_path for hit in hits] == ["new.md"]


async def test_get_chunks_returns_ordered_chunks_for_one_document(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunks = [
        Chunk(text="third", source_path="a.md", page=1, source_hash="h1", index=2),
        Chunk(text="first", source_path="a.md", page=1, source_hash="h1", index=0),
        Chunk(text="second", source_path="a.md", page=1, source_hash="h1", index=1),
        Chunk(text="other doc", source_path="b.md", page=1, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    result = await store.get_chunks("h1", TENANT)

    assert [c.text for c in result] == ["first", "second", "third"]
    assert all(c.source_hash == "h1" for c in result)


async def test_get_chunks_unknown_hash_returns_empty(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    assert await store.get_chunks("does-not-exist", TENANT) == []


async def test_list_documents_includes_modified_at_and_indexed_at(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    """D44: the documents-listing path must surface the file's true mtime (temporal-knowledge
    plumbing) — ``indexed_at`` (a store-assigned recency stamp) rides along too."""
    await store.ensure_ready(MODEL, dim, TENANT)
    chunk = Chunk(
        text="a one",
        source_path="a.md",
        page=1,
        source_hash="h1",
        index=0,
        modified_at="2026-02-03T04:05:06+00:00",
    )
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (doc,) = await store.list_documents(TENANT)

    assert doc.modified_at == "2026-02-03T04:05:06+00:00"
    assert doc.indexed_at is not None


async def test_list_documents_modified_at_is_none_when_never_provided(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunk = Chunk(text="a one", source_path="a.md", page=1, source_hash="h1", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (doc,) = await store.list_documents(TENANT)

    assert doc.modified_at is None


async def test_get_chunks_includes_modified_at(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    """D44: each chunk carries its parent file's ``modified_at`` alongside its ``metadata``."""
    await store.ensure_ready(MODEL, dim, TENANT)
    chunk = Chunk(
        text="dated",
        source_path="a.md",
        page=1,
        source_hash="h1",
        index=0,
        modified_at="2026-05-06T07:08:09+00:00",
        metadata={"k": "v"},
    )
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (result,) = await store.get_chunks("h1", TENANT)

    assert result.modified_at == "2026-05-06T07:08:09+00:00"
    assert result.metadata == {"k": "v"}


async def test_list_documents_metadata_filter_narrows_to_matching_docs(
    store: FakeVectorStore, embedder: FakeEmbedder, dim: int
) -> None:
    await store.ensure_ready(MODEL, dim, TENANT)
    chunks = [
        Chunk(
            text="a one",
            source_path="a.md",
            page=1,
            source_hash="h1",
            index=0,
            metadata={"project": "condense"},
        ),
        Chunk(text="b one", source_path="b.md", page=1, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    docs = await store.list_documents(TENANT, metadata={"project": "condense"})

    assert [d.source_hash for d in docs] == ["h1"]


async def test_tenant_isolation(store: FakeVectorStore, embedder: FakeEmbedder, dim: int) -> None:
    await store.ensure_ready(MODEL, dim, "tenant-a")
    chunk = Chunk(text="only in a", source_path="a.md", page=1, source_hash="ha", index=0)
    await store.upsert([await _embedded(embedder, chunk)], "tenant-a")

    await store.ensure_ready(MODEL, dim, "tenant-b")
    (query,) = await embedder.embed(["only in a"])
    assert await store.search(query, 5, "tenant-b") == []
    assert await store.known_hashes("tenant-b") == set()

    assert await store.known_hashes("tenant-a") == {"ha"}
