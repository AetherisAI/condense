"""The judge phase: which metrics apply, failure handling, abstention parsing, RAGAS mapping."""

from __future__ import annotations

import pytest

from sift.adapters.llm.fake import FakeCompleter
from sift.eval.golden import GoldenItem
from sift.eval.judge import (
    AbstentionCheck,
    FakeJudge,
    JudgeSample,
    applicable,
    judge_results,
    strip_citations,
)
from sift.eval.ragas_judge import _ReferenceRecall
from sift.eval.records import Passage, SurfaceResult

ANSWERABLE = GoldenItem(id="a", question="How long?", reference="Two days.")
NO_REFERENCE = GoldenItem(id="b", question="Why?")
UNANSWERABLE = GoldenItem(id="c", question="Who won in 1900?", answerable=False)


def _result(item_id: str, **fields: object) -> SurfaceResult:
    defaults: dict[str, object] = {
        "response": "It takes two days.",
        "contexts": [Passage(path="a.md", page=1, text="two days")],
    }
    return SurfaceResult(item_id=item_id, surface="find", **{**defaults, **fields})  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize(
    ("metric", "sample", "expected"),
    [
        ("answer_relevancy", JudgeSample(question="q", response="r"), True),
        ("answer_relevancy", JudgeSample(question="q", response="  "), False),
        ("faithfulness", JudgeSample(question="q", response="r"), False),
        ("faithfulness", JudgeSample(question="q", response="r", contexts=("c",)), True),
        ("answer_correctness", JudgeSample(question="q", response="r"), False),
        ("answer_correctness", JudgeSample(question="q", response="r", reference="x"), True),
        ("answer_recall", JudgeSample(question="q", response="r"), False),
        ("answer_recall", JudgeSample(question="q", response="r", reference="x"), True),
        ("noise_sensitivity", JudgeSample(question="q", response="r", reference="x"), False),
    ],
)
def test_applicable(metric: str, sample: JudgeSample, expected: bool) -> None:
    assert applicable(metric, sample) is expected


async def test_judge_results_scores_applicable_metrics_only() -> None:
    judge = FakeJudge({"faithfulness": 0.9, "answer_correctness": None})
    rows = [_result("a"), _result("b"), _result("c"), _result("a", error="boom")]
    items = {i.id: i for i in (ANSWERABLE, NO_REFERENCE, UNANSWERABLE)}

    await judge_results(rows, items, judge=judge, abstention=None)

    assert rows[0].scores == {
        "answer_relevancy": 0.5,
        "faithfulness": 0.9,
        "answer_correctness": None,  # the judge failed → recorded as missing, not dropped
        "answer_recall": 0.5,
        "context_utilization": 0.5,
        "noise_sensitivity": 0.5,
    }
    assert set(rows[1].scores) == {"answer_relevancy", "faithfulness", "context_utilization"}
    assert rows[2].scores == {}  # unanswerable: no answer metrics
    assert rows[3].scores == {}  # collection failed: nothing to judge


async def test_abstention_runs_on_every_item() -> None:
    rows = [_result("a"), _result("c", response="The documents don't cover this.")]
    items = {i.id: i for i in (ANSWERABLE, UNANSWERABLE)}

    await judge_results(rows, items, judge=None, abstention=AbstentionCheck(FakeCompleter("NO")))

    assert rows[0].scores == {"abstained": 0.0}
    assert rows[1].scores == {"abstained": 0.0}


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [("YES", 1.0), ("yes.", 1.0), ("**No**", 0.0), ("NO, it answers", 0.0), ("maybe", None)],
)
async def test_abstention_parses_one_word_verdicts(verdict: str, expected: float | None) -> None:
    check = AbstentionCheck(FakeCompleter(verdict))

    assert await check.abstained("q", "r") == expected


async def test_abstention_judge_failure_is_none() -> None:
    assert await AbstentionCheck(FakeCompleter(raises=True)).abstained("q", "r") is None


# --- RAGAS adapter (only when the optional [eval] extra is installed) --------------------------


class _Result:
    def __init__(self, value: float) -> None:
        self.value = value


class _StubMetric:
    def __init__(self, value: float | Exception) -> None:
        self.value = value
        self.kwargs: dict[str, object] = {}

    async def ascore(self, **kwargs: object) -> _Result:
        self.kwargs = kwargs
        if isinstance(self.value, Exception):
            raise self.value
        return _Result(self.value)


def _ragas_judge():
    pytest.importorskip("ragas")
    from sift.eval.ragas_judge import RagasJudge

    return RagasJudge(
        base_url="http://judge.invalid/v1",
        model="judge",
        api_key="",
        embed_base_url="http://embed.invalid/v1",
        embed_model="bge-m3",
        embed_api_key="",
    )


def test_ragas_judge_builds_every_metric_without_network() -> None:
    judge = _ragas_judge()

    assert set(judge._metrics) == {
        "answer_relevancy",
        "faithfulness",
        "answer_correctness",
        "answer_recall",
        "context_utilization",
        "noise_sensitivity",
    }
    assert judge.name.startswith("ragas 0.4")
    assert isinstance(judge._metrics["answer_recall"], _ReferenceRecall)


async def test_ragas_judge_maps_sample_onto_ascore_kwargs() -> None:
    judge = _ragas_judge()
    stub = _StubMetric(0.75)
    judge._metrics["noise_sensitivity"] = stub
    sample = JudgeSample(question="q", response="r", contexts=("c1", "c2"), reference="ref")

    assert await judge.score(sample, "noise_sensitivity") == 0.75
    assert stub.kwargs == {
        "user_input": "q",
        "response": "r",
        "reference": "ref",
        "retrieved_contexts": ["c1", "c2"],
    }


async def test_ragas_judge_answer_recall_takes_response_and_reference_only() -> None:
    judge = _ragas_judge()
    stub = _StubMetric(1.0)
    judge._metrics["answer_recall"] = stub
    sample = JudgeSample(question="q", response="r", contexts=("c",), reference="ref")

    assert await judge.score(sample, "answer_recall") == 1.0
    assert stub.kwargs == {"response": "r", "reference": "ref"}


class _StubFactualCorrectness:
    def __init__(self, verdicts: list[bool]) -> None:
        self.verdicts = verdicts
        self.args: tuple[str, str] | None = None

    async def _decompose_and_verify_claims(self, text: str, premise: str) -> list[bool]:
        self.args = (text, premise)
        return self.verdicts


async def test_answer_recall_is_the_share_of_reference_claims_the_response_states() -> None:
    # The live case behind D84: RAGAS's recall mode scored this correct answer 0.
    stub = _StubFactualCorrectness([True, False])

    result = await _ReferenceRecall(stub).ascore(
        response="FrostyGoop uses TCP port 502.", reference="Port 502. It speaks Modbus."
    )

    assert result.value == 0.5
    # The reference is decomposed; the response is only the premise, its extras never count.
    assert stub.args == ("Port 502. It speaks Modbus.", "FrostyGoop uses TCP port 502.")


async def test_answer_recall_with_no_reference_claims_is_none() -> None:
    judge = _ragas_judge()
    judge._metrics["answer_recall"] = _ReferenceRecall(_StubFactualCorrectness([]))

    sample = JudgeSample(question="q", response="r", reference="ref")
    assert await judge.score(sample, "answer_recall") is None


@pytest.mark.parametrize("value", [ValueError("unparseable judge output"), float("nan")])
async def test_ragas_judge_failure_or_nan_is_none(value: float | Exception) -> None:
    judge = _ragas_judge()
    judge._metrics["faithfulness"] = _StubMetric(value)

    sample = JudgeSample(question="q", response="r", contexts=("c",))
    assert await judge.score(sample, "faithfulness") is None


def test_ragas_judge_anthropic_provider_sends_no_sampling_params() -> None:
    # D82: Claude Haiku 5.5 rejects `temperature` and `top_p` (RAGAS sends 0.01 / 0.1), and
    # the OpenAI-compatible endpoint rejects the JSON mode RAGAS uses — so Anthropic judges go
    # through the native SDK (structured output via tool use) with both params dropped.
    pytest.importorskip("ragas")
    pytest.importorskip("anthropic")
    from sift.eval.ragas_judge import RagasJudge

    judge = RagasJudge(
        base_url="https://api.anthropic.com/v1",
        model="claude-haiku-5-5",
        api_key="k",
        embed_base_url="http://embed.invalid/v1",
        embed_model="bge-m3",
        embed_api_key="",
        provider="anthropic",
    )

    llm = judge._metrics["faithfulness"].llm
    assert llm.provider == "anthropic"
    assert llm.model_args == {"max_tokens": 4096}
    # The OpenAI-compatible URL (used by the abstention check) minus `/v1` is the SDK's root.
    assert str(llm.client.client.base_url).rstrip("/") == "https://api.anthropic.com"


def test_ragas_judge_requires_a_judge_model() -> None:
    pytest.importorskip("ragas")
    from sift.eval.ragas_judge import RagasJudge

    with pytest.raises(RuntimeError, match="no judge LLM configured"):
        RagasJudge(
            base_url="",
            model="",
            api_key="",
            embed_base_url="",
            embed_model="",
            embed_api_key="",
        )


# --- citation stripping (D76) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Ask's inline style, single and multi-source.
        (
            "Express orders arrive the next business day (policies/shipping.md, p.1).",
            "Express orders arrive the next business day.",
        ),
        ("27 days in total (hr/a.md, p.1; hr/b.md, p.2).", "27 days in total."),
        # Find recap styles: numbered markers and a trailing attribution line.
        ("Refunds take 2-3 days [1, 2].", "Refunds take 2-3 days."),
        ("Yes, up to five days.\nSource: [1]", "Yes, up to five days."),
        ("**Sources:** [1], [2]", ""),
        # Content that merely looks parenthetical or mentions sources is kept.
        ("See the guide (e.g. section 3).", "See the guide (e.g. section 3)."),
        ("Free (for orders above 50 euros).", "Free (for orders above 50 euros)."),
        ("Sources: the 2026 policy and the FAQ", "Sources: the 2026 policy and the FAQ"),
    ],
)
def test_strip_citations(raw: str, expected: str) -> None:
    assert strip_citations(raw) == expected


async def test_judge_sees_stripped_response_unless_disabled() -> None:
    row = _result("a", response="It takes two days (a.md, p.1).")

    stripping, verbatim = FakeJudge(), FakeJudge()
    await judge_results([row], {"a": ANSWERABLE}, judge=stripping, abstention=None)
    await judge_results([row], {"a": ANSWERABLE}, judge=verbatim, abstention=None, strip=False)

    assert {s.response for _, s in stripping.calls} == {"It takes two days."}
    assert {s.response for _, s in verbatim.calls} == {"It takes two days (a.md, p.1)."}
    assert row.response == "It takes two days (a.md, p.1)."  # the stored answer is never touched
