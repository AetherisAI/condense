"""The noise sweep: gold located, distractors never gold, ratios honoured, seeded and judged."""

from __future__ import annotations

import random

from sift.eval.collect import collect_find
from sift.eval.config import EvalSettings
from sift.eval.golden import GoldenItem, GoldRef
from sift.eval.judge import FakeJudge
from sift.eval.noise import build_context, gold_passages, run_noise_sweep
from sift.eval.records import Passage
from sift.factory import Container

ITEM = GoldenItem(
    id="ship",
    question="express shipping arrives the next business day",
    reference="Next business day.",
    relevant=(GoldRef(path="shipping.md", evidence="arrives the next business day"),),
)


def _p(name: str) -> Passage:
    return Passage(path=f"{name}.md", page=1, text=name)


def test_build_context_counts() -> None:
    gold, noise = [_p("g")], [_p("n1"), _p("n2"), _p("n3")]

    for ratio, expected in [(0.0, (1, 0)), (0.25, (1, 1)), (0.5, (1, 2)), (0.75, (1, 3))]:
        context, n_gold, n_noise = build_context(gold, noise, ratio, 4, random.Random(0))
        assert (n_gold, n_noise) == expected
        assert len(context) == n_gold + n_noise


def test_build_context_never_drops_the_last_gold_and_caps_noise() -> None:
    context, n_gold, n_noise = build_context([_p("g")], [_p("n1")], 0.75, 4, random.Random(0))

    assert (n_gold, n_noise) == (1, 1)  # only one distractor available
    assert _p("g") in context


def test_build_context_shuffle_is_seeded() -> None:
    gold, noise = [_p("g")], [_p(f"n{i}") for i in range(3)]

    first, *_ = build_context(gold, noise, 0.75, 4, random.Random("seed"))
    second, *_ = build_context(gold, noise, 0.75, 4, random.Random("seed"))

    assert first == second


async def test_gold_passages_finds_the_evidence_chunk(container: Container) -> None:
    passages = await gold_passages(container, ITEM, None, EvalSettings(), {})

    # shipping.md has two chunks — only page 2 carries the evidence.
    assert [(p.path, p.page) for p in passages] == [("policies/shipping.md", 2)]


async def test_gold_passages_path_only_ref_uses_retrieval(container: Container) -> None:
    item = GoldenItem(id="r", question="refunds take two", relevant=(GoldRef(path="refunds.md"),))
    find_row = await collect_find(container, item, EvalSettings())

    passages = await gold_passages(container, item, find_row, EvalSettings(), {})

    assert [p.path for p in passages] == ["policies/refunds.md"]


async def test_sweep_keeps_gold_docs_out_of_distractors_and_judges(container: Container) -> None:
    es = EvalSettings(noise_ratios="0,0.5", noise_context_size=2)
    find_row = await collect_find(container, ITEM, es)
    judge = FakeJudge({"answer_correctness": 0.8})

    trials, skipped = await run_noise_sweep(container, [ITEM], {ITEM.id: find_row}, es, judge)

    assert skipped == []
    assert [(t.ratio, t.n_gold, t.n_noise) for t in trials] == [(0.0, 1, 0), (0.5, 1, 1)]
    noisy = trials[1]
    gold_doc = [p for p in noisy.contexts if p.path == "policies/shipping.md"]
    assert len(gold_doc) == 1 and gold_doc[0].page == 2  # the other shipping chunk isn't noise
    assert noisy.response.startswith("Question: express shipping")  # recapped via the real prompt
    assert noisy.scores == {"answer_correctness": 0.8, "faithfulness": 0.5}


async def test_sweep_skips_items_without_locatable_gold(container: Container) -> None:
    missing = GoldenItem(
        id="ghost",
        question="q",
        reference="r",
        relevant=(GoldRef(path="nowhere.md", evidence="nothing"),),
    )

    trials, skipped = await run_noise_sweep(container, [missing], {}, EvalSettings(), None)

    assert trials == [] and skipped == ["ghost"]
