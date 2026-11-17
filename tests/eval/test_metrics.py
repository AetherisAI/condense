"""Retrieval metrics and latency stats — hand-computed expectations on tiny rankings."""

from __future__ import annotations

import math

import pytest

from sift.eval.golden import GoldRef
from sift.eval.metrics import chunk_scores, doc_scores, latency_stats, mean_scores, percentile
from sift.eval.records import Passage


def _p(path: str, text: str = "", page: int = 1) -> Passage:
    return Passage(path=path, page=page, text=text)


def test_chunk_scores_single_gold() -> None:
    ranking = [_p("a.md", "noise"), _p("b.md", "the answer is 42"), _p("c.md", "noise")]
    refs = [GoldRef(path="b.md", evidence="answer is 42")]

    scores = chunk_scores(ranking, refs, ks=[1, 3], threshold=0.6)

    assert scores == {
        "recall@1": 0.0,
        "complete@1": 0.0,
        "precision@1": 0.0,
        "hit@1": 0.0,
        "recall@3": 1.0,
        "complete@3": 1.0,
        "precision@3": pytest.approx(1 / 3),
        "hit@3": 1.0,
        "mrr": 0.5,
    }


def test_chunk_scores_two_gold_refs_partial_recall() -> None:
    ranking = [_p("a.md", "first fact here"), _p("x.md"), _p("y.md")]
    refs = [GoldRef(path="a.md", evidence="first fact"), GoldRef(path="b.md")]

    scores = chunk_scores(ranking, refs, ks=[3], threshold=0.6)

    assert scores is not None
    assert scores["recall@3"] == 0.5
    assert scores["mrr"] == 1.0


def test_chunk_level_respects_evidence_but_doc_level_does_not() -> None:
    # Right document, wrong passage: doc level credits it, chunk level doesn't.
    ranking = [_p("a.md", "an unrelated paragraph"), _p("a.md", "the real evidence")]
    refs = [GoldRef(path="a.md", evidence="the real evidence")]

    chunk = chunk_scores(ranking, refs, ks=[1], threshold=0.6)
    doc = doc_scores(ranking, refs, ks=[1])

    assert chunk is not None and doc is not None
    assert chunk["hit@1"] == 0.0 and chunk["mrr"] == 0.5
    assert doc["hit@1"] == 1.0 and doc["mrr"] == 1.0


def test_doc_scores_dedupe_by_path_before_ranking() -> None:
    ranking = [_p("a.md"), _p("a.md"), _p("a.md"), _p("b.md")]
    refs = [GoldRef(path="b.md")]

    scores = doc_scores(ranking, refs, ks=[2])

    # b.md is the 2nd DISTINCT document, not the 4th passage.
    assert scores is not None
    assert scores["hit@2"] == 1.0
    assert scores["mrr"] == 0.5


def test_no_gold_refs_means_undefined() -> None:
    assert chunk_scores([_p("a.md")], [], ks=[1], threshold=0.6) is None
    assert doc_scores([_p("a.md")], [], ks=[1]) is None


def test_empty_ranking_scores_zero() -> None:
    scores = doc_scores([], [GoldRef(path="a.md")], ks=[5])

    assert scores == {
        "recall@5": 0.0,
        "complete@5": 0.0,
        "precision@5": 0.0,
        "hit@5": 0.0,
        "mrr": 0.0,
    }


def test_alternatives_in_one_group_need_only_one_hit() -> None:
    # Two files that each state the answer: finding either one is full recall.
    ranking = [_p("tactic.md", "T0884 Connection Proxy"), _p("x.md")]
    refs = [
        GoldRef(path="technique.md", evidence="act as an intermediary", group="a"),
        GoldRef(path="tactic.md", evidence="T0884 Connection Proxy", group="a"),
    ]

    for scores in (
        chunk_scores(ranking, refs, ks=[1], threshold=0.6),
        doc_scores(ranking, refs, [1]),
    ):
        assert scores is not None
        assert scores["recall@1"] == 1.0 and scores["complete@1"] == 1.0
        assert scores["hit@1"] == 1.0 and scores["precision@1"] == 1.0


def test_required_groups_each_count_and_complete_needs_all() -> None:
    # Multi-hop: fact A has two alternative sources, fact B one; only A is retrieved.
    ranking = [_p("a2.md", "fact a"), _p("x.md"), _p("y.md")]
    refs = [
        GoldRef(path="a1.md", evidence="fact a", group="A"),
        GoldRef(path="a2.md", evidence="fact a", group="A"),
        GoldRef(path="b.md", evidence="fact b"),
    ]

    scores = chunk_scores(ranking, refs, ks=[3], threshold=0.6)

    assert scores is not None
    assert scores["recall@3"] == 0.5  # 1 of 2 required groups, not 1 of 3 refs
    assert scores["complete@3"] == 0.0
    assert scores["hit@3"] == 1.0 and scores["mrr"] == 1.0


def test_two_hits_inside_one_group_still_count_once() -> None:
    # Retrieving both alternatives can't push recall past what one would give.
    ranking = [_p("a1.md", "fact a"), _p("a2.md", "fact a"), _p("x.md")]
    refs = [
        GoldRef(path="a1.md", evidence="fact a", group="A"),
        GoldRef(path="a2.md", evidence="fact a", group="A"),
        GoldRef(path="b.md", evidence="fact b"),
    ]

    scores = chunk_scores(ranking, refs, ks=[3], threshold=0.6)

    assert scores is not None
    assert scores["recall@3"] == 0.5 and scores["complete@3"] == 0.0
    assert scores["precision@3"] == pytest.approx(2 / 3)  # both passages are relevant


def test_mean_scores_skips_undefined_rows_and_nan() -> None:
    rows = [{"mrr": 1.0, "x": math.nan}, None, {"mrr": 0.0, "x": 0.5}]

    assert mean_scores(rows) == {"mrr": 0.5, "x": 0.5}


def test_percentile_interpolates() -> None:
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 25.0
    assert percentile([10.0], 0.95) == 10.0
    assert math.isnan(percentile([], 0.5))


def test_latency_stats() -> None:
    stats = latency_stats([30.0, 10.0, 20.0, math.nan])

    assert stats == {"n": 3, "mean": 20.0, "p50": 20.0, "p95": pytest.approx(29.0), "max": 30.0}
    assert latency_stats([]) == {"n": 0}
