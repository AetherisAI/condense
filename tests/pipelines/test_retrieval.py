"""Unit tests for :mod:`sift.pipelines.retrieval`: reciprocal-rank fusion and ``retrieve``."""

from __future__ import annotations

import math
from collections.abc import Sequence

import pytest

from sift.core.types import Chunk, Hit, SearchFilters, Vector
from sift.pipelines.retrieval import (
    RRF_K,
    FusionWeights,
    SupportsKeywordSearch,
    fuse,
    is_keyword_style,
    retrieve,
)

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
    hits = await retrieve(store, "q", (1.0,), 5, TENANT, filters, mode="hybrid")
    assert _names(hits) == ["shared", "v1", "k1"]
    assert store.keyword_calls == [("q", 5, filters)]


async def test_retrieve_vector_mode_never_runs_the_keyword_search() -> None:
    store = _KeywordStore([_hit("v1")], [_hit("k1")])
    hits = await retrieve(store, "q", (1.0,), 5, TENANT, mode="vector")
    assert _names(hits) == ["v1"]
    assert store.keyword_calls == []


async def test_retrieve_keyword_mode_returns_only_keyword_matches() -> None:
    store = _KeywordStore([_hit("v1"), _hit("shared")], [_hit("shared"), _hit("k1")])
    filters = SearchFilters(since="2026-01-01")
    hits = await retrieve(store, "q", (1.0,), 5, TENANT, filters, mode="keyword")
    assert _names(hits) == ["shared", "k1"]
    assert store.keyword_calls == [("q", 5, filters)]


async def test_retrieve_keyword_mode_with_no_match_returns_nothing() -> None:
    # An explicit keyword search means "passages containing these words": none is an answer.
    store = _KeywordStore([_hit("v1")], [])
    assert await retrieve(store, "q", (1.0,), 5, TENANT, mode="keyword") == []


async def test_retrieve_is_vector_only_for_a_store_without_keyword_search() -> None:
    for mode in ("hybrid", "keyword"):
        hits = await retrieve(_Store([_hit("v1")], None), "q", (1.0,), 5, TENANT, mode=mode)
        assert _names(hits) == ["v1"]


async def test_retrieve_keeps_vector_order_when_no_keyword_matches() -> None:
    store = _KeywordStore([_hit("v1"), _hit("v2")], [])
    hits = await retrieve(store, "q", (1.0,), 5, TENANT, mode="hybrid")
    assert _names(hits) == ["v1", "v2"]


# --- weighted fusion ------------------------------------------------------------------------


def test_fuse_weights_scale_each_lists_contribution() -> None:
    # Equal weights: the lists interleave, the first list winning each tie. At weight 2 even the
    # keyword list's second hit (2/62) beats the vector list's first (1/61).
    vector, keyword = [_hit("a"), _hit("b")], [_hit("k"), _hit("c")]
    assert _names(fuse([vector, keyword], k=10)) == ["a", "k", "b", "c"]
    assert _names(fuse([vector, keyword], k=10, weights=[1.0, 2.0])) == ["k", "c", "a", "b"]


def test_fuse_weighted_score_is_the_weighted_reciprocal_rank_sum() -> None:
    # b: 1/(60+2) from the first list + 3/(60+1) from the second beats a's 1/(60+1).
    fused = fuse([[_hit("a"), _hit("b")], [_hit("b")]], k=10, weights=[1.0, 3.0])
    assert _names(fused) == ["b", "a"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("T1553 tactic", True),
        ("OnionDuke group years backup C2", True),
        ("rundll32.exe", True),
        ("What tactic is T1553 part of?", False),  # a question
        ("Welche Technik verbirgt sich hinter T0884?", False),  # a question in German
        ("how to reset the admin password", False),  # English function words
        ("", False),
        ("   ", False),
    ],
)
def test_is_keyword_style(query: str, expected: bool) -> None:
    assert is_keyword_style(query) is expected


def test_fusion_weights_pick_the_keyword_style_weight_for_keyword_queries() -> None:
    weights = FusionWeights(keyword=1.0, keyword_style=2.5)
    assert weights.keyword_weight("T1553 tactic") == 2.5
    assert weights.keyword_weight("What tactic is T1553 part of?") == 1.0


async def test_retrieve_applies_the_keyword_weight_for_the_query() -> None:
    store = _KeywordStore([_hit("v1"), _hit("v2")], [_hit("k1"), _hit("k2")])
    weights = FusionWeights(keyword=1.0, keyword_style=2.0)

    question = await retrieve(
        store, "which file mentions it?", (1.0,), 5, TENANT, mode="hybrid", weights=weights
    )
    keywords = await retrieve(
        store, "zephyrium datasheet", (1.0,), 5, TENANT, mode="hybrid", weights=weights
    )

    assert _names(question)[0] == "v1"  # plain fusion: the vector list's top wins the tie
    assert _names(keywords)[0] == "k1"  # keyword-style: the keyword list counts double


async def test_retrieve_defaults_to_plain_fusion() -> None:
    store = _KeywordStore([_hit("v1")], [_hit("k1")])
    hits = await retrieve(store, "zephyrium datasheet", (1.0,), 5, TENANT, mode="hybrid")
    assert _names(hits) == ["v1", "k1"]
