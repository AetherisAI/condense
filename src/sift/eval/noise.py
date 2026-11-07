"""Noise robustness: does Find's recap stay correct as irrelevant passages crowd the context?

A controlled sweep over the recap stage alone (retrieval is held fixed, so this isolates the
generator's robustness — RAG-benchmark "noise robustness"). Per answerable item with a reference:

1. **Gold passages** — one per required group of gold refs (alternatives share a group, D78):
   the gold document's first chunk matching the ref's page/evidence; for a path-only ref, the
   best-ranked retrieved chunk from that document. A group's first locatable ref stands for it,
   so two files that state the same answer don't both crowd into the context.
2. **Distractors** — this question's own retrieved passages from NON-gold documents, in rank
   order (hard negatives: on-topic but not the answer), topped up with other questions'
   non-gold passages in seeded random order.
3. For each noise ratio ``r``: ``n_noise = round(N·r)`` distractors plus up to ``N − n_noise``
   gold passages (at least one), shuffled with a per-(seed, item, r) RNG, recapped through
   :meth:`~sift.pipelines.search.SearchPipeline.recap` — the production prompt — then scored
   with answer correctness and faithfulness. With fewer gold passages than slots the context is
   shorter, so each trial also records its *actual* ratio.

The headline: ``robustness = correctness@highest_ratio ÷ correctness@0``.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

from sift.eval.collect import Progress
from sift.eval.config import EvalSettings
from sift.eval.corpus import document_passages, list_documents, resolve
from sift.eval.golden import GoldenItem, GoldRef, ref_groups
from sift.eval.judge import Judge, make_sample
from sift.eval.matching import passage_matches, path_matches
from sift.eval.records import Passage, SurfaceResult
from sift.factory import Container

NOISE_METRICS: tuple[str, ...] = ("answer_correctness", "faithfulness")


@dataclass(slots=True, kw_only=True)
class NoiseTrial:
    item_id: str
    ratio: float
    n_gold: int
    n_noise: int
    response: str = ""
    contexts: list[Passage] = field(default_factory=list)
    scores: dict[str, float | None] = field(default_factory=dict)
    error: str | None = None

    @property
    def actual_ratio(self) -> float:
        total = self.n_gold + self.n_noise
        return self.n_noise / total if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "actual_ratio": self.actual_ratio}


def _is_gold_doc(passage: Passage, refs: Sequence[GoldRef]) -> bool:
    return any(path_matches(passage.path, ref.path) for ref in refs)


async def gold_passages(
    container: Container,
    item: GoldenItem,
    find_row: SurfaceResult | None,
    es: EvalSettings,
    doc_chunks: dict[str, list[Passage]],
) -> list[Passage]:
    """One passage per required group (see module docstring); groups that can't be located are
    skipped."""
    docs = None

    async def locate(ref: GoldRef) -> Passage | None:
        nonlocal docs
        if ref.page is None and ref.evidence is None:
            if find_row is None:
                return None
            return next((p for p in find_row.retrieved if path_matches(p.path, ref.path)), None)
        if docs is None:
            docs = await list_documents(container, es.tenant)
        for doc in resolve(ref.path, docs):
            if doc.source_hash not in doc_chunks:
                doc_chunks[doc.source_hash] = await document_passages(
                    container, doc.source_hash, es.tenant
                )
            passage = next(
                (
                    p
                    for p in doc_chunks[doc.source_hash]
                    if passage_matches(p, ref, es.evidence_match_threshold)
                ),
                None,
            )
            if passage:
                return passage
        return None

    found: list[Passage] = []
    for group in ref_groups(item.relevant):
        for index in group:
            passage = await locate(item.relevant[index])
            if passage is not None:
                if passage not in found:
                    found.append(passage)
                break
    return found


def build_context(
    gold: Sequence[Passage],
    distractors: Sequence[Passage],
    ratio: float,
    size: int,
    rng: random.Random,
) -> tuple[list[Passage], int, int]:
    """``(shuffled context, n_gold, n_noise)`` for one trial."""
    n_noise = min(round(size * ratio), len(distractors))
    n_gold = max(1, min(len(gold), size - n_noise))
    context = [*gold[:n_gold], *distractors[:n_noise]]
    rng.shuffle(context)
    return context, n_gold, n_noise


async def run_noise_sweep(
    container: Container,
    items: Sequence[GoldenItem],
    find_rows: Mapping[str, SurfaceResult],
    es: EvalSettings,
    judge: Judge | None,
    progress: Progress | None = None,
) -> tuple[list[NoiseTrial], list[str]]:
    """Every eligible item × ratio. Returns the trials and the ids skipped (no gold located)."""
    say = progress or (lambda _msg: None)
    eligible = [i for i in items if i.answerable and i.reference and i.relevant]
    shared = random.Random(es.seed)
    other_negatives = [
        p
        for item in eligible
        for p in (find_rows[item.id].retrieved if item.id in find_rows else [])
    ]
    shared.shuffle(other_negatives)
    doc_chunks: dict[str, list[Passage]] = {}

    trials: list[NoiseTrial] = []
    skipped: list[str] = []
    for item in eligible:
        find_row = find_rows.get(item.id)
        gold = await gold_passages(container, item, find_row, es, doc_chunks)
        if not gold:
            skipped.append(item.id)
            continue
        own = [
            p
            for p in (find_row.retrieved if find_row else [])
            if not _is_gold_doc(p, item.relevant)
        ]
        extra = [p for p in other_negatives if not _is_gold_doc(p, item.relevant) and p not in own]
        distractors = own + extra
        for ratio in es.ratios:
            rng = random.Random(f"{es.seed}:{item.id}:{ratio}")
            context, n_gold, n_noise = build_context(
                gold, distractors, ratio, es.noise_context_size, rng
            )
            trial = NoiseTrial(
                item_id=item.id, ratio=ratio, n_gold=n_gold, n_noise=n_noise, contexts=context
            )
            try:
                trial.response = await container.search.recap(
                    item.question, [p.to_hit() for p in context]
                )
            except Exception as exc:  # noqa: BLE001 — one failed recap must not sink the sweep
                trial.error = f"{type(exc).__name__}: {exc}"
            trials.append(trial)
        say(f"[noise] {item.id}: {len(es.ratios)} ratios, {len(gold)} gold passage(s)")

    if judge is not None:
        await judge_trials(trials, eligible, judge, es.judge_concurrency, es.strip_citations)
    return trials, skipped


async def judge_trials(
    trials: Sequence[NoiseTrial],
    items: Sequence[GoldenItem],
    judge: Judge,
    concurrency: int,
    strip: bool = True,
) -> None:
    """Score each successful trial on :data:`NOISE_METRICS`, in place, ``concurrency`` at once."""
    gate = asyncio.Semaphore(concurrency)
    by_id = {i.id: i for i in items}

    async def score(trial: NoiseTrial, metric: str) -> None:
        item = by_id[trial.item_id]
        sample = make_sample(
            question=item.question,
            response=trial.response,
            contexts=[p.text for p in trial.contexts],
            reference=item.reference,
            strip=strip,
        )
        async with gate:
            trial.scores[metric] = await judge.score(sample, metric)

    await asyncio.gather(
        *(
            score(t, m)
            for t in trials
            if t.item_id in by_id and not t.error and t.response.strip()
            for m in NOISE_METRICS
        )
    )
