"""The judge phase: LLM-graded answer metrics behind a small :class:`Judge` protocol.

The real judge is :class:`~sift.eval.ragas_judge.RagasJudge` (RAGAS collections metrics, an
optional extra); tests use :class:`FakeJudge`. Scores land in each
:attr:`~sift.eval.records.SurfaceResult.scores` under the metric's name:

- a metric that doesn't apply to a sample (no reference → no answer correctness; no contexts →
  no faithfulness) is **omitted**;
- a metric the judge failed to compute (unparseable judge output, provider error) is **None** —
  counted in the report, never a crash.

**Two correctness scores.** ``answer_correctness`` is RAGAS's claim F1 (+ similarity): an
answer loses points both for reference facts it misses *and* for true details the reference
doesn't list, so it moves with verbosity. ``answer_recall`` asks only whether the answer
contains the reference's facts — with a reference that holds just what the question asks, that's
"did it answer correctly", whatever else it adds. Unsupported extras are faithfulness's job. It
reuses RAGAS ``FactualCorrectness``'s prompts but not its recall arithmetic. Likewise,
``noise_sensitivity`` judges a claim correct against the question + reference, not the bare
reference.

Separately, :class:`AbstentionCheck` asks the judge LLM whether a response declined to answer,
recorded as ``abstained`` (1.0/0.0) on every result: on ``answerable: false`` items that's the
correct-abstention rate, on answerable ones the false-refusal rate.

**Citations are stripped before judging.** Both surfaces cite their sources inline —
``(policies/shipping.md, p.1)``, ``[1]``, a trailing ``Source: [1]`` line — and RAGAS counts
each as a claim the passages don't support: measured live, a correct one-sentence Ask answer
scored faithfulness 0.5 with its citation and 1.0 without. :func:`strip_citations` removes those
markers from the judged copy only (the stored response stays verbatim); ``EVAL_STRIP_CITATIONS=
false`` turns it off.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from sift.core.ports import Completer
from sift.eval.collect import Progress
from sift.eval.golden import GoldenItem
from sift.eval.records import SurfaceResult

METRICS: tuple[str, ...] = (
    "answer_relevancy",
    "faithfulness",
    "answer_correctness",
    "answer_recall",
    "context_utilization",
    "noise_sensitivity",
)
# Higher is better for every metric except noise sensitivity (fraction of wrong claims).
LOWER_IS_BETTER = frozenset({"noise_sensitivity"})
_NEEDS_CONTEXTS = frozenset({"faithfulness", "context_utilization", "noise_sensitivity"})
_NEEDS_REFERENCE = frozenset({"answer_correctness", "answer_recall", "noise_sensitivity"})


@dataclass(frozen=True, slots=True, kw_only=True)
class JudgeSample:
    question: str
    response: str
    contexts: tuple[str, ...] = ()
    reference: str | None = None


_DOC_EXT = r"(?:md|markdown|txt|pdf|docx?|pptx?|xlsx?|csv|tsv|html?|json|rtf|odt|eml)"
# `(policies/shipping.md, p.1)`, `(hr/a.md, p.1; hr/b.md, p.2)`, `(p. 3)` — a parenthetical that
# names a document file or a page is a citation, not content.
_PAREN_CITATION = re.compile(
    rf"\s*\((?=[^()]*(?:\.{_DOC_EXT}\b|\bp(?:age)?\.?\s*\d))[^()]*\)", re.IGNORECASE
)
# `[1]`, `[1, 3]`, `[2-4]`
_BRACKET_CITATION = re.compile(r"\s*\[\d+(?:\s*[,;–-]\s*\d+)*\]")
# A line that is nothing but an attribution once the markers above are gone: `Source: [1]`.
_SOURCE_LINE = re.compile(
    r"^\s*[*_]*(?:sources?|references?|citations?|cited)[*_]*\s*:[\s,;.*_]*$", re.IGNORECASE
)


def strip_citations(text: str) -> str:
    """``text`` without inline source citations — see the module docstring."""
    text = _BRACKET_CITATION.sub("", _PAREN_CITATION.sub("", text))
    lines = [line for line in text.splitlines() if not _SOURCE_LINE.match(line)]
    return re.sub(r"\s+([.,;:!?])", r"\1", "\n".join(lines)).strip()


def make_sample(
    *,
    question: str,
    response: str,
    contexts: Sequence[str],
    reference: str | None,
    strip: bool = True,
) -> JudgeSample:
    return JudgeSample(
        question=question,
        response=strip_citations(response) if strip else response,
        contexts=tuple(contexts),
        reference=reference,
    )


def applicable(metric: str, sample: JudgeSample) -> bool:
    if not sample.response.strip():
        return False
    if metric in _NEEDS_CONTEXTS and not sample.contexts:
        return False
    if metric in _NEEDS_REFERENCE and not sample.reference:
        return False
    return True


class Judge(Protocol):
    @property
    def name(self) -> str: ...

    async def score(self, sample: JudgeSample, metric: str) -> float | None: ...


@dataclass(slots=True)
class FakeJudge:
    """Returns ``scores[metric]`` (default 0.5) and records every ``(metric, sample)`` call."""

    scores: Mapping[str, float | None] = field(default_factory=dict)
    calls: list[tuple[str, JudgeSample]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return "fake"

    async def score(self, sample: JudgeSample, metric: str) -> float | None:
        self.calls.append((metric, sample))
        return self.scores.get(metric, 0.5)


_ABSTENTION_SYSTEM = (
    "You grade one assistant response. Reply with exactly one word.\n"
    "Reply YES if the response declines to answer: it says the documents or sources don't "
    "contain or cover the answer, that it can't find it, or that it doesn't know.\n"
    "Reply NO if the response gives a substantive answer to the question, even a partial one."
)


class AbstentionCheck:
    """Did the response decline? A one-word YES/NO judgment from the judge ``Completer``."""

    def __init__(self, completer: Completer) -> None:
        self._completer = completer

    async def abstained(self, question: str, response: str) -> float | None:
        try:
            verdict = await self._completer.complete(
                _ABSTENTION_SYSTEM, f"Question: {question}\n\nResponse:\n{response}"
            )
        except Exception:  # noqa: BLE001 — a judge failure is a missing score, never a crash
            return None
        word = verdict.strip().strip(".!*\"'").split(maxsplit=1)
        if not word:
            return None
        if word[0].upper().startswith("YES"):
            return 1.0
        if word[0].upper().startswith("NO"):
            return 0.0
        return None


def sample_for(result: SurfaceResult, item: GoldenItem, strip: bool = True) -> JudgeSample:
    return make_sample(
        question=item.question,
        response=result.response,
        contexts=[p.text for p in result.contexts],
        reference=item.reference,
        strip=strip,
    )


async def judge_results(
    results: Sequence[SurfaceResult],
    items: Mapping[str, GoldenItem],
    *,
    judge: Judge | None,
    abstention: AbstentionCheck | None,
    metrics: Sequence[str] = METRICS,
    concurrency: int = 4,
    strip: bool = True,
    progress: Progress | None = None,
) -> None:
    """Fill ``scores`` on every successfully-collected result, in place, ``concurrency`` at a time.

    Answer metrics run only for answerable items (an unanswerable item has no correct answer to
    be faithful to or correct against); abstention runs for every item.
    """
    gate = asyncio.Semaphore(concurrency)
    say = progress or (lambda _msg: None)

    async def one_metric(result: SurfaceResult, sample: JudgeSample, metric: str) -> None:
        assert judge is not None
        async with gate:
            result.scores[metric] = await judge.score(sample, metric)

    async def one_abstention(result: SurfaceResult, item: GoldenItem) -> None:
        assert abstention is not None
        async with gate:
            result.scores["abstained"] = await abstention.abstained(item.question, result.response)

    tasks = []
    for result in results:
        item = items.get(result.item_id)
        if item is None or result.error or not result.response.strip():
            continue
        sample = sample_for(result, item, strip)
        if judge is not None and item.answerable:
            tasks.extend(one_metric(result, sample, m) for m in metrics if applicable(m, sample))
        if abstention is not None:
            tasks.append(one_abstention(result, item))
    say(f"judging: {len(tasks)} scoring calls, {concurrency} at a time")
    await asyncio.gather(*tasks)
