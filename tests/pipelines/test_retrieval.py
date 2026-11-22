"""Unit tests for :mod:`sift.pipelines.retrieval`: reciprocal-rank fusion and ``retrieve``."""

from __future__ import annotations

import math
from collections.abc import Sequence

from sift.core.types import Chunk, Hit, SearchFilters, Vector
from sift.pipelines.retrieval import RRF_K, SupportsKeywordSearch, fuse, retrieve

TENANT = "default"


def _hit(name: str, score: float = 0.5) -> Hit:
    return Hit(text=name, score=score, source_path=f"{name}.md", page=1, source_hash=name, index=0)


def _names(hits: list[Hit]) -> list[str]:
    return [hit.source_hash for hit in hits]


class _Store:
    """A store with fixed vector and keyword rankings that records the calls it gets."""

    def __init__(self, by_vector: list[Hit], by_keyword: list[Hit] | None) -> None:
        self._by_vector = by_vector
        self._by_keyword = by_keyword
        self.keyword_calls: list[tuple[str, int, SearchFilters | None]] = []

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None: ...

    async def upsert(self, chunks: Sequence[Chunk], tenant: str) -> None: ...

    async def known_hashes(self, tenant: str) -> set[str]:
        return set()

    async def search(
        self, vector: Vector, k: int, tenant: str, filters: SearchFilters | None = None
    ) -> list[Hit]:
        return self._by_vector[:k]


class _KeywordStore(_Store):
    async def keyword_search(
        self,
        query: str,
        vector: Vector,
        k: int,
        tenant: str,
        filters: SearchFilters | None = None,
    ) -> list[Hit]:
        self.keyword_calls.append((query, k, filters))
        return (self._by_keyword or [])[:k]


def test_fuse_scores_each_chunk_by_summed_reciprocal_rank() -> None:
    # b is 2nd and 1st: 1/62 + 1/61 beats a (1st, absent) and c (absent, 2nd).
    fused = fuse([[_hit("a"), _hit("b")], [_hit("b"), _hit("c")]], k=10)
    assert _names(fused) == ["b", "a", "c"]


def test_fuse_puts_a_chunk_in_both_lists_ahead_of_either_list_top() -> None:
    by_vector = [_hit("v1"), _hit("v2"), _hit("both")]
    by_keyword = [_hit("k1"), _hit("k2"), _hit("both")]
    # 2 / (RRF_K + 3) > 1 / (RRF_K + 1): agreement outweighs one list's first place.
    assert 2 / (RRF_K + 3) > 1 / (RRF_K + 1)
    assert _names(fuse([by_vector, by_keyword], k=10))[0] == "both"


def test_fuse_breaks_ties_in_favour_of_the_first_list() -> None:
    assert _names(fuse([[_hit("v")], [_hit("k")]], k=10)) == ["v", "k"]


def test_fuse_keeps_the_first_lists_copy_and_score() -> None:
    fused = fuse([[_hit("a", score=0.9)], [_hit("a", score=0.1)]], k=10)
    assert len(fused) == 1
    assert math.isclose(fused[0].score, 0.9)


def test_fuse_identifies_chunks_by_source_hash_and_index() -> None:
    first = Hit(text="x", score=0.5, source_path="d.md", page=1, source_hash="d", index=0)
    second = Hit(text="y", score=0.5, source_path="d.md", page=1, source_hash="d", index=1)
    assert len(fuse([[first], [second]], k=10)) == 2


def test_fuse_caps_at_k() -> None:
    assert len(fuse([[_hit(str(i)) for i in range(5)], [_hit("x")]], k=3)) == 3


def test_keyword_store_satisfies_the_capability() -> None:
    assert isinstance(_KeywordStore([], []), SupportsKeywordSearch)
    assert not isinstance(_Store([], []), SupportsKeywordSearch)


async def test_retrieve_fuses_when_hybrid() -> None:
    store = _KeywordStore([_hit("v1"), _hit("shared")], [_hit("shared"), _hit("k1")])
    filters = SearchFilters(metadata={"kind": "note"})
    hits = await retrieve(store, "q", (1.0,), 5, TENANT, filters, hybrid=True)
    assert _names(hits) == ["shared", "v1", "k1"]
    assert store.keyword_calls == [("q", 5, filters)]


async def test_retrieve_is_vector_only_when_hybrid_is_off() -> None:
    store = _KeywordStore([_hit("v1")], [_hit("k1")])
    hits = await retrieve(store, "q", (1.0,), 5, TENANT, hybrid=False)
    assert _names(hits) == ["v1"]
    assert store.keyword_calls == []


async def test_retrieve_is_vector_only_for_a_store_without_keyword_search() -> None:
    hits = await retrieve(_Store([_hit("v1")], None), "q", (1.0,), 5, TENANT, hybrid=True)
    assert _names(hits) == ["v1"]


async def test_retrieve_keeps_vector_order_when_no_keyword_matches() -> None:
    store = _KeywordStore([_hit("v1"), _hit("v2")], [])
    hits = await retrieve(store, "q", (1.0,), 5, TENANT, hybrid=True)
    assert _names(hits) == ["v1", "v2"]
