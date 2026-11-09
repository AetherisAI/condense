"""hit@k, recall@k and MRR checked three independent ways.

1. **Hand-computed tables** — tiny rankings whose expected values are worked out by hand from the
   textbook definitions and written into the test, so a reader can check the arithmetic.
2. **Differential test against an oracle** — :func:`_oracle` re-derives each metric straight from
   its definition (by path, with plain lists and sets, sharing no code with
   :mod:`sift.eval.metrics`) and must agree with the real functions on a few hundred seeded random
   rankings. Seeded, so a failure reproduces exactly from the case number in the message.
3. **Invariants** — relations every correct implementation satisfies whatever the input (bounds,
   monotone in k, hit@k ⇔ MRR ≥ 1/k, shifting the ranking down one rank, ...): a second net in
   case the oracle and the code share a misreading of the definitions.

Relevance is kept unambiguous: every gold ref gets its own slash-free path and is matched on path
alone, so these tests are about ranking arithmetic, not evidence matching (``test_matching.py``).
"""

from __future__ import annotations

import random
from collections.abc import Sequence

import pytest

from sift.eval.golden import GoldRef
from sift.eval.metrics import Scores, chunk_scores, doc_scores, mean_scores
from sift.eval.records import Passage

KS = [1, 3, 5, 10]
NOISE = [f"noise-{c}.md" for c in "abcdefghijkl"]
THRESHOLD = 0.6


def _ranking(paths: Sequence[str], page: int = 1) -> list[Passage]:
    return [Passage(path=path, page=page, text="") for path in paths]


def _gold_at(rank: int | None, length: int = 5, gold: str = "gold.md") -> list[Passage]:
    """``length`` noise passages, with ``gold`` at 1-based ``rank`` (``None``: not retrieved)."""
    paths = NOISE[:length]
    if rank is not None:
        paths[rank - 1] = gold
    return _ranking(paths)


def _both_levels(ranking: list[Passage], refs: list[GoldRef], ks: Sequence[int]) -> list[Scores]:
    """Chunk and doc scores; with path-only refs and distinct paths the two must coincide."""
    chunk = chunk_scores(ranking, refs, ks, THRESHOLD)
    doc = doc_scores(ranking, refs, ks)
    assert chunk is not None and doc is not None
    return [chunk, doc]


# --- 1. hand-computed tables -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("rank", "hits", "mrr"),
    [
        #       hit@1 hit@3 hit@5 hit@10   1 / rank
        (1, (1.0, 1.0, 1.0, 1.0), 1.0),
        (2, (0.0, 1.0, 1.0, 1.0), 1 / 2),
        (3, (0.0, 1.0, 1.0, 1.0), 1 / 3),
        (5, (0.0, 0.0, 1.0, 1.0), 1 / 5),
        (None, (0.0, 0.0, 0.0, 0.0), 0.0),
    ],
)
def test_single_gold_ref_at_each_rank(
    rank: int | None, hits: tuple[float, ...], mrr: float
) -> None:
    refs = [GoldRef(path="gold.md")]

    for scores in _both_levels(_gold_at(rank), refs, KS):
        assert [scores[f"hit@{k}"] for k in KS] == list(hits)
        # One required piece of evidence, so recall@k is exactly hit@k.
        assert [scores[f"recall@{k}"] for k in KS] == list(hits)
        assert scores["mrr"] == pytest.approx(mrr)


@pytest.mark.parametrize(
    ("paths", "recalls", "hits", "mrr"),
    [
        # gold a, b, c at ranks 1, 4, 6
        (
            ["a.md", "n1", "n2", "b.md", "n3", "c.md", "n4"],
            (1 / 3, 1 / 3, 2 / 3, 1.0),
            (1.0, 1.0, 1.0, 1.0),
            1.0,
        ),
        # first gold at rank 4, so nothing in the top 3
        (
            ["n1", "n2", "n3", "a.md", "b.md", "n4", "c.md"],
            (0.0, 0.0, 2 / 3, 1.0),
            (0.0, 0.0, 1.0, 1.0),
            1 / 4,
        ),
        # c is never retrieved: recall tops out at 2/3 while hit is already 1
        (
            ["n1", "b.md", "n2", "n3", "n4", "a.md"],
            (0.0, 1 / 3, 1 / 3, 2 / 3),
            (0.0, 1.0, 1.0, 1.0),
            1 / 2,
        ),
    ],
)
def test_three_required_refs(
    paths: list[str], recalls: tuple[float, ...], hits: tuple[float, ...], mrr: float
) -> None:
    refs = [GoldRef(path="a.md"), GoldRef(path="b.md"), GoldRef(path="c.md")]

    for scores in _both_levels(_ranking(paths), refs, KS):
        assert [scores[f"recall@{k}"] for k in KS] == pytest.approx(list(recalls))
        assert [scores[f"hit@{k}"] for k in KS] == list(hits)
        assert scores["mrr"] == pytest.approx(mrr)


def test_mrr_uses_only_the_first_relevant_rank() -> None:
    # Later relevant passages neither raise it (no averaging of 1/2, 1/3, 1/4) nor lower it.
    refs = [GoldRef(path="gold.md")]
    one = chunk_scores(_ranking(["n", "gold.md", "n", "n"]), refs, KS, THRESHOLD)
    many = chunk_scores(_ranking(["n", "gold.md", "gold.md", "gold.md"]), refs, KS, THRESHOLD)

    assert one is not None and many is not None
    assert one["mrr"] == many["mrr"] == 0.5


def test_mrr_is_not_cut_at_k() -> None:
    # MRR runs over everything retrieved; only hit@k / recall@k stop at k.
    scores = doc_scores(_gold_at(8, length=10), [GoldRef(path="gold.md")], [1, 5])

    assert scores is not None
    assert scores["hit@5"] == 0.0 and scores["recall@5"] == 0.0
    assert scores["mrr"] == pytest.approx(1 / 8)


def test_k_beyond_the_ranking_length() -> None:
    # Two passages, k = 10: the window is just shorter; nothing breaks or extrapolates.
    scores = chunk_scores(_ranking(["n", "gold.md"]), [GoldRef(path="gold.md")], [10], THRESHOLD)

    assert scores is not None
    assert scores["hit@10"] == 1.0 and scores["recall@10"] == 1.0 and scores["mrr"] == 0.5


def test_chunk_recall_counts_distinct_evidence_not_passages() -> None:
    # Gold: page 1 and page 2 of one file. Retrieving page 1 three times is still half the evidence.
    refs = [GoldRef(path="a.md", page=1), GoldRef(path="a.md", page=2)]
    ranking = _ranking(["a.md"] * 3, page=1)

    scores = chunk_scores(ranking, refs, [3], THRESHOLD)

    assert scores is not None
    assert scores["recall@3"] == 0.5
    assert scores["hit@3"] == 1.0 and scores["mrr"] == 1.0


def test_mean_reciprocal_rank_textbook_example() -> None:
    # The standard worked example (Wikipedia, "Mean reciprocal rank"): first correct answer
    # at ranks 3, 2 and 1 → MRR = (1/3 + 1/2 + 1) / 3 = 11/18.
    refs = [GoldRef(path="gold.md")]
    per_query = [doc_scores(_gold_at(rank), refs, KS) for rank in (3, 2, 1)]

    run = mean_scores(per_query)

    assert run["mrr"] == pytest.approx(11 / 18)
    assert run["hit@1"] == pytest.approx(1 / 3)  # 1 of 3 queries has it first
    assert run["hit@3"] == 1.0


def test_run_mean_counts_misses_and_skips_unanswerable_items() -> None:
    refs = [GoldRef(path="gold.md")]
    per_query = [
        doc_scores(_gold_at(1), refs, KS),
        doc_scores(_gold_at(None), refs, KS),  # answerable but missed: scores 0, still counted
        doc_scores(_gold_at(1), [], KS),  # no gold refs: undefined, left out of the mean
    ]

    run = mean_scores(per_query)

    assert run["mrr"] == 0.5 and run["hit@1"] == 0.5 and run["recall@10"] == 0.5


def test_run_recall_is_macro_averaged_per_question() -> None:
    # Q1 finds 1 of its 2 refs, Q2 its only ref: macro mean (1/2 + 1) / 2 = 3/4,
    # not the pooled 2 of 3 refs = 2/3.
    q1 = doc_scores(_ranking(["a.md", "n"]), [GoldRef(path="a.md"), GoldRef(path="b.md")], [2])
    q2 = doc_scores(_ranking(["c.md", "n"]), [GoldRef(path="c.md")], [2])

    assert mean_scores([q1, q2])["recall@2"] == pytest.approx(3 / 4)


# --- 2. differential test against an independent oracle --------------------------------------

ORACLE_KS = [1, 2, 3, 5, 10, 20]  # 20 > the longest random ranking
CASES = 400


def _oracle(paths: list[str], refs: list[GoldRef], ks: Sequence[int], *, docs: bool) -> Scores:
    """hit@k, recall@k and MRR straight from their definitions, matching gold on path equality."""
    if docs:  # doc level: a document's first occurrence keeps its rank, repeats are dropped
        paths = [p for i, p in enumerate(paths) if p not in paths[:i]]
    gold_paths = {ref.path for ref in refs}
    # required evidence: refs sharing a label are alternatives, an unlabelled ref stands alone
    required: dict[object, set[str]] = {}
    for i, ref in enumerate(refs):
        required.setdefault(ref.group if ref.group is not None else ("alone", i), set()).add(
            ref.path
        )
    out: Scores = {}
    for k in ks:
        top = set(paths[:k])
        out[f"hit@{k}"] = 1.0 if top & gold_paths else 0.0
        out[f"recall@{k}"] = sum(1 for alts in required.values() if alts & top) / len(required)
    relevant_ranks = [rank for rank, p in enumerate(paths, start=1) if p in gold_paths]
    out["mrr"] = 1 / relevant_ranks[0] if relevant_ranks else 0.0
    return out


def _random_case(rng: random.Random) -> tuple[list[str], list[GoldRef]]:
    gold = [f"gold-{c}.md" for c in "abcd"[: rng.randint(1, 4)]]
    refs = [GoldRef(path=p, group=rng.choice([None, None, "x", "y"])) for p in gold]
    pool = gold + NOISE[: rng.randint(2, len(NOISE))]
    # repeats allowed: several chunks of one file, which only the doc level collapses
    paths = [rng.choice(pool) for _ in range(rng.randint(0, 15))]
    return paths, refs


def _cases() -> list[tuple[int, list[str], list[GoldRef]]]:
    rng = random.Random(20261109)
    return [(n, *_random_case(rng)) for n in range(CASES)]


def _metrics(scores: Scores) -> Scores:
    return {k: v for k, v in scores.items() if k.split("@")[0] in {"hit", "recall", "mrr"}}


def test_oracle_agrees_with_the_hand_tables() -> None:
    # Check the checker: the oracle must reproduce a worked example before it judges anything.
    paths = ["n1", "n2", "n3", "a.md", "b.md", "n4", "c.md"]
    refs = [GoldRef(path="a.md"), GoldRef(path="b.md"), GoldRef(path="c.md")]

    assert _oracle(paths, refs, KS, docs=False) == pytest.approx(
        {
            "hit@1": 0.0, "hit@3": 0.0, "hit@5": 1.0, "hit@10": 1.0,
            "recall@1": 0.0, "recall@3": 0.0, "recall@5": 2 / 3, "recall@10": 1.0,
            "mrr": 1 / 4,
        }
    )  # fmt: skip


def test_matches_the_oracle_on_random_rankings() -> None:
    misses = hits_first = 0
    for n, paths, refs in _cases():
        ranking = _ranking(paths)
        chunk = chunk_scores(ranking, refs, ORACLE_KS, THRESHOLD)
        doc = doc_scores(ranking, refs, ORACLE_KS)
        assert chunk is not None and doc is not None
        where = f"case {n}: paths={paths} refs={refs}"

        assert _metrics(chunk) == pytest.approx(_oracle(paths, refs, ORACLE_KS, docs=False)), where
        assert _metrics(doc) == pytest.approx(_oracle(paths, refs, ORACLE_KS, docs=True)), where
        misses += chunk["mrr"] == 0.0
        hits_first += chunk["mrr"] == 1.0

    # The generator must exercise both extremes and everything between, or the test is hollow.
    assert misses > CASES // 20 and hits_first > CASES // 20
    assert CASES - misses - hits_first > CASES // 4


# --- 3. invariants ---------------------------------------------------------------------------


def test_invariants_hold_on_random_rankings() -> None:
    for n, paths, refs in _cases():
        for scores in (
            chunk_scores(_ranking(paths), refs, ORACLE_KS, THRESHOLD),
            doc_scores(_ranking(paths), refs, ORACLE_KS),
        ):
            assert scores is not None
            where = f"case {n}: paths={paths} refs={refs} scores={scores}"
            mrr = scores["mrr"]
            assert 0.0 <= mrr <= 1.0, where
            assert (scores["hit@1"] == 1.0) == (mrr == 1.0), where
            for k, wider in zip(ORACLE_KS, ORACLE_KS[1:], strict=False):
                assert scores[f"hit@{k}"] <= scores[f"hit@{wider}"], where
                assert scores[f"recall@{k}"] <= scores[f"recall@{wider}"], where
            for k in ORACLE_KS:
                hit, recall = scores[f"hit@{k}"], scores[f"recall@{k}"]
                assert hit in (0.0, 1.0) and 0.0 <= recall <= 1.0, where
                assert (hit == 1.0) == (recall > 0.0), where  # any relevant ⇔ some evidence
                assert (hit == 1.0) == (mrr >= 1 / k), where  # first relevant within top k


def test_pushing_the_ranking_down_one_rank() -> None:
    # A noise passage on top moves every rank by one: hit@(k+1) inherits hit@k and the first
    # relevant rank r becomes r + 1, so MRR 1/r becomes 1/(r + 1).
    for n, paths, refs in _cases():
        before = doc_scores(_ranking(paths), refs, ORACLE_KS)
        after = doc_scores(_ranking(["pushed-down.md", *paths]), refs, [k + 1 for k in ORACLE_KS])
        assert before is not None and after is not None
        where = f"case {n}: paths={paths} refs={refs}"

        for k in ORACLE_KS:
            assert after[f"hit@{k + 1}"] == before[f"hit@{k}"], where
            assert after[f"recall@{k + 1}"] == before[f"recall@{k}"], where
        expected = 1 / (1 / before["mrr"] + 1) if before["mrr"] else 0.0
        assert after["mrr"] == pytest.approx(expected), where


def test_appending_below_k_changes_nothing_at_k() -> None:
    # Whatever is retrieved after rank k can't move hit@k or recall@k — and once something
    # relevant is found, nothing appended later can move MRR either.
    rng = random.Random(7)
    for n, paths, refs in _cases():
        tail = [rng.choice([*NOISE, *(r.path for r in refs)]) for _ in range(5)]
        ks = [k for k in ORACLE_KS if k <= len(paths)]
        before = chunk_scores(_ranking(paths), refs, ORACLE_KS, THRESHOLD)
        after = chunk_scores(_ranking(paths + tail), refs, ORACLE_KS, THRESHOLD)
        assert before is not None and after is not None
        where = f"case {n}: paths={paths} tail={tail} refs={refs}"

        for k in ks:
            assert after[f"hit@{k}"] == before[f"hit@{k}"], where
            assert after[f"recall@{k}"] == before[f"recall@{k}"], where
        if before["mrr"]:
            assert after["mrr"] == before["mrr"], where
