"""Retrieval metrics and latency statistics — pure functions, no I/O, no LLM.

Definitions (per golden item, then averaged over the items where they're defined):

- **recall@k** — required evidence found in the top-k ÷ required evidence. "Required evidence"
  is a *group* of gold refs (:func:`~sift.eval.golden.ref_groups`): alternatives that each state
  the answer share a group, and one of them is enough; an unlabelled ref is its own group, so a
  set without ``group`` labels scores exactly as before.
- **complete@k** — 1 if *every* group is found in the top-k, else 0: for a multi-hop question,
  did retrieval surface everything the answer needs?
- **precision@k** — relevant passages in the top-k ÷ k (the standard ``/k`` form, so one gold
  document caps doc-level precision@5 at 0.2 — compare runs, not against 1.0). A passage is
  relevant if it matches any gold ref; groups don't change it.
- **hit@k** — 1 if any gold ref is in the top-k, else 0. hit@1 on the final ranking is the
  product's own question: did ``/search`` return the right thing?
- **MRR** — 1 ÷ rank of the first relevant passage (0 when none is retrieved).

**Chunk level** matches each passage against path + page + evidence. **Doc level** first
dedupes the ranking by path (first occurrence keeps its rank) and matches on path alone.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from sift.eval.golden import GoldRef, ref_groups
from sift.eval.matching import normalize_path, passage_matches, path_matches
from sift.eval.records import Passage

Scores = dict[str, float]


def _scores(
    matched: Sequence[set[int]], groups: Sequence[tuple[int, ...]], ks: Sequence[int]
) -> Scores:
    """Score a ranking given, per rank, the set of gold-ref indices that passage satisfies."""
    out: Scores = {}
    for k in ks:
        window = matched[:k]
        found = set().union(*window) if window else set()
        covered = sum(1 for group in groups if found.intersection(group))
        out[f"recall@{k}"] = covered / len(groups)
        out[f"complete@{k}"] = 1.0 if covered == len(groups) else 0.0
        out[f"precision@{k}"] = sum(1 for m in window if m) / k
        out[f"hit@{k}"] = 1.0 if found else 0.0
    first = next((rank for rank, m in enumerate(matched, start=1) if m), None)
    out["mrr"] = 1.0 / first if first else 0.0
    return out


def chunk_scores(
    ranking: Sequence[Passage], refs: Sequence[GoldRef], ks: Sequence[int], threshold: float
) -> Scores | None:
    if not refs:
        return None
    matched = [
        {i for i, ref in enumerate(refs) if passage_matches(p, ref, threshold)} for p in ranking
    ]
    return _scores(matched, ref_groups(refs), ks)


def doc_scores(
    ranking: Sequence[Passage], refs: Sequence[GoldRef], ks: Sequence[int]
) -> Scores | None:
    if not refs:
        return None
    seen: set[str] = set()
    docs: list[str] = []
    for passage in ranking:
        key = normalize_path(passage.path)
        if key not in seen:
            seen.add(key)
            docs.append(passage.path)
    matched = [{i for i, ref in enumerate(refs) if path_matches(doc, ref.path)} for doc in docs]
    return _scores(matched, ref_groups(refs), ks)


def mean_scores(rows: Iterable[Scores | None]) -> Scores:
    """Key-wise mean over the defined rows (``None`` rows and NaN values are skipped)."""
    totals: dict[str, list[float]] = {}
    for row in rows:
        if row is None:
            continue
        for key, value in row.items():
            if value is not None and not math.isnan(value):
                totals.setdefault(key, []).append(value)
    return {key: sum(values) / len(values) for key, values in totals.items()}


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile ``q`` ∈ [0, 1] of already-sorted values."""
    if not sorted_values:
        return math.nan
    position = (len(sorted_values) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return sorted_values[low]
    weight = position - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def latency_stats(values: Iterable[float]) -> dict[str, float]:
    ordered = sorted(v for v in values if not math.isnan(v))
    if not ordered:
        return {"n": 0}
    return {
        "n": len(ordered),
        "mean": sum(ordered) / len(ordered),
        "p50": percentile(ordered, 0.5),
        "p95": percentile(ordered, 0.95),
        "max": ordered[-1],
    }
