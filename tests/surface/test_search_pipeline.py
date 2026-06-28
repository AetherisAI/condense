"""Unit tests for :class:`~sift.pipelines.search.SearchPipeline` (fakes only, offline).

Drives the query path end-to-end through ``FakeEmbedder`` + ``FakeVectorStore`` +
``NullReranker`` + ``NullCompleter``: the exact-match best chunk surfaces as the single
``Source`` (M1), an empty base yields the "No results found." recap, and a source-level
grep guards the dependency rule (the pipeline must compose ports, never import an adapter).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.llm.null import NullCompleter
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings
from sift.core.types import Chunk
from sift.pipelines.search import SearchPipeline

MODEL = "bge-m3"
TENANT = "default"


def _settings() -> Settings:
    return Settings(ingest_token="t", final_k=1, retrieve_k=30)


async def _seed(store: FakeVectorStore, embedder: FakeEmbedder, chunks: list[Chunk]) -> None:
    """Pin the base and upsert ``chunks`` carrying their deterministic FakeEmbedder vectors."""
    await store.ensure_ready(MODEL, embedder.dim, TENANT)
    vectors = await embedder.embed([chunk.text for chunk in chunks])
    embedded = [
        replace(chunk, vector=vector)
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    await store.upsert(embedded, TENANT)


async def test_search_returns_single_best_source() -> None:
    embedder = FakeEmbedder()
    store = FakeVectorStore()
    chunks = [
        Chunk(
            text="alpha passage about cats",
            source_path="cats.md",
            page=1,
            source_hash="h1",
            index=0,
        ),
        Chunk(
            text="beta passage about dogs",
            source_path="dogs.md",
            page=2,
            source_hash="h2",
            index=0,
        ),
    ]
    await _seed(store, embedder, chunks)
    pipeline = SearchPipeline(embedder, store, NullReranker(), NullCompleter(), _settings())

    response = await pipeline.search("beta passage about dogs")

    # FINAL_K == 1 → exactly one citation, and the exact-match chunk wins (cosine ≈ 1.0).
    (source,) = response.sources
    assert source.path == "dogs.md"
    assert source.page == 2
    assert source.score == pytest.approx(1.0)
    # The matched passage + its ordinal are surfaced (the "where in the doc" hint).
    assert source.snippet == "beta passage about dogs"
    assert source.index == 0
    # NullCompleter echoes the recap user turn — it carries the query and the cited passage.
    assert response.summary.startswith("Question: beta passage about dogs")
    assert "beta passage about dogs" in response.summary


class _CapturingCompleter:
    """Records the (system, user) turns it is asked to complete."""

    def __init__(self) -> None:
        self.system = ""
        self.user = ""

    async def complete(self, system: str, user: str) -> str:
        self.system, self.user = system, user
        return "recap"


async def test_recap_sees_query_and_top_passages() -> None:
    embedder = FakeEmbedder()
    store = FakeVectorStore()
    chunks = [
        Chunk(
            text=f"passage number {i} about topic {i}",
            source_path=f"d{i}.md",
            page=1,
            source_hash=f"h{i}",
            index=i,
        )
        for i in range(3)
    ]
    await _seed(store, embedder, chunks)
    completer = _CapturingCompleter()
    settings = Settings(ingest_token="t", final_k=1, retrieve_k=30, recap_context_k=3)
    pipeline = SearchPipeline(embedder, store, NullReranker(), completer, settings)

    await pipeline.search("passage number 1 about topic 1")

    # The recap user turn leads with the question and includes all top-K passages as context.
    assert completer.user.startswith("Question: passage number 1 about topic 1")
    for i in range(3):
        assert f"passage number {i} about topic {i}" in completer.user


async def test_empty_store_returns_no_results() -> None:
    pipeline = SearchPipeline(
        FakeEmbedder(), FakeVectorStore(), NullReranker(), NullCompleter(), _settings()
    )

    response = await pipeline.search("anything")

    assert response.summary == "No results found."
    assert response.sources == []


def test_search_pipeline_imports_no_adapter() -> None:
    import sift.pipelines.search as search_module

    source = Path(search_module.__file__).read_text(encoding="utf-8")
    assert "sift.adapters" not in source
