"""Tests for :class:`~sift.adapters.cache.embedding.CachingEmbedder`, the query-embedding cache."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from sift.adapters.cache.embedding import CachingEmbedder
from sift.adapters.embedding.fake import FakeEmbedder
from sift.core.ports import Embedder
from sift.core.types import Vector


class _CountingEmbedder:
    """Wraps the fake embedder and records every batch it is asked to embed."""

    def __init__(self) -> None:
        self._fake = FakeEmbedder(dim=8)
        self.calls: list[list[str]] = []
        self.fail_next = False

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        self.calls.append(list(texts))
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("embedding server down")
        return await self._fake.embed(texts)


def test_satisfies_the_embedder_port() -> None:
    impl: Embedder = CachingEmbedder(FakeEmbedder(), max_entries=4)
    assert isinstance(impl, Embedder)


async def test_a_repeated_text_is_embedded_once() -> None:
    inner = _CountingEmbedder()
    embedder = CachingEmbedder(inner, max_entries=4)

    first = await embedder.embed(["phishing"])
    second = await embedder.embed(["phishing"])

    assert first == second
    assert inner.calls == [["phishing"]]


async def test_only_the_misses_reach_the_inner_embedder_in_order() -> None:
    inner = _CountingEmbedder()
    embedder = CachingEmbedder(inner, max_entries=8)
    await embedder.embed(["b"])

    out = await embedder.embed(["a", "b", "c", "a"])

    assert inner.calls == [["b"], ["a", "c"]]
    assert out == await FakeEmbedder(dim=8).embed(["a", "b", "c", "a"])


async def test_cached_vectors_are_exact_tuples() -> None:
    inner = _CountingEmbedder()
    embedder = CachingEmbedder(inner, max_entries=4)
    (fresh,) = await embedder.embed(["exact"])

    (cached,) = await embedder.embed(["exact"])

    assert isinstance(cached, tuple)
    assert cached == fresh


async def test_a_failure_is_not_cached() -> None:
    inner = _CountingEmbedder()
    embedder = CachingEmbedder(inner, max_entries=4)
    inner.fail_next = True

    with pytest.raises(RuntimeError):
        await embedder.embed(["retry me"])
    await embedder.embed(["retry me"])

    assert inner.calls == [["retry me"], ["retry me"]]


async def test_an_empty_batch_skips_the_inner_embedder() -> None:
    inner = _CountingEmbedder()

    assert await CachingEmbedder(inner, max_entries=4).embed([]) == []
    assert inner.calls == []
