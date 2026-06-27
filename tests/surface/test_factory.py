"""Unit tests for :func:`~sift.factory.build_container` — the single composition root.

With no external base URLs configured the factory must wire the *fake* adapters, so the
container's ``.search`` runs fully offline through ``FakeEmbedder`` + ``FakeVectorStore`` +
``NullReranker``; ``rerank_strategy`` then selects the matching :class:`~sift.core.ports.Reranker`
adapter. No network is touched — the default container is self-contained.
"""

from __future__ import annotations

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.llm.null import NullCompleter
from sift.adapters.rerank.crossencoder_http import CrossEncoderReranker
from sift.adapters.rerank.llm_judge import LlmJudgeReranker
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings
from sift.factory import Container, build_container


def test_build_container_defaults_to_fakes() -> None:
    container = build_container(Settings(ingest_token="t"))

    assert isinstance(container, Container)
    assert container.settings.ingest_token == "t"
    # No EMBED/LLM base URL and no Turso URL → the offline fakes, not the HTTP adapters.
    assert isinstance(container.search._embedder, FakeEmbedder)
    assert isinstance(container.search._store, FakeVectorStore)
    assert isinstance(container.search._reranker, NullReranker)
    assert isinstance(container.search._completer, NullCompleter)


async def test_default_container_search_runs_offline() -> None:
    container = build_container(Settings(ingest_token="t"))

    # Empty fake store → the pipeline short-circuits without any network call.
    response = await container.search.search("anything")

    assert response.summary == "No results found."
    assert response.sources == []


def test_rerank_strategy_llm_selects_llm_judge() -> None:
    container = build_container(Settings(ingest_token="t", rerank_strategy="llm"))

    assert isinstance(container.search._reranker, LlmJudgeReranker)


def test_rerank_strategy_crossencoder_selects_crossencoder() -> None:
    container = build_container(
        Settings(
            ingest_token="t",
            rerank_strategy="crossencoder",
            rerank_base_url="http://tei.local",
        )
    )

    assert isinstance(container.search._reranker, CrossEncoderReranker)
