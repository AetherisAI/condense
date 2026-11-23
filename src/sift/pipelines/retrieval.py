"""First-stage retrieval: vector search, plus keyword search when the store has it, fused.

Embeddings and keywords fail on different questions. Embeddings find a paraphrase that shares
no words with the passage; a keyword index finds the exact identifier, product name or error
code that an embedding blurs into its neighbours. On the MITRE ATT&CK benchmark either one
alone ranks the right document first about 70% of the time, and the two fused 76%.

The lists are merged by weighted reciprocal-rank fusion: each chunk scores
``sum(weight / (RRF_K + rank))`` over the lists it appears in. It uses ranks only, so BM25 scores
and cosine similarities never need to be put on one scale. Each fused hit keeps the cosine
similarity its store reported, so ``Hit.score`` still means "how close is this to the query" for
every hit; only the order changes.

The keyword list's weight depends on how the query is written. A keyword-style query, with no
question mark and no English stopword ("T1553 tactic", "OnionDuke backup C2"), is someone
typing the terms they expect to find, so the keyword match deserves more say than for a
question. On MITRE ATT&CK without a reranker, doubling the keyword weight for those queries
ranked the right document first for 6 more of 306 questions and for none fewer; with the
reranker it makes no difference, since the cross-encoder re-sorts the shortlist anyway. Raising
the weight for every query instead cost top-3 hits and German questions, which BM25 can't match
against English text.

Three modes (``SEARCH_MODE``, or per request in the toolbox search): ``hybrid`` fuses both
lists, ``vector`` uses embeddings alone, and ``keyword`` uses the keyword index alone, returning
only passages that contain the query's words (an exact identifier, error code or name). Keyword
search is a capability, like :class:`~sift.pipelines.documents.SupportsDocumentAdmin`: a store
without it serves every mode from vectors alone.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, get_args, runtime_checkable

from sift.config import SearchMode, Settings
from sift.core.ports import VectorStore
from sift.core.text import STOPWORDS, words
from sift.core.types import Hit, SearchFilters, Vector

SEARCH_MODES: tuple[SearchMode, ...] = get_args(SearchMode)

# The constant from the paper that introduced RRF (Cormack, Clarke and Buettcher, 2009). It
# flattens the gap between the first few ranks so that neither list's top hit dominates.
RRF_K = 60

# A question mark marks a question in most scripts; the full-width form covers CJK input.
_QUESTION_MARKS = ("?", "\uff1f")


def is_keyword_style(query: str) -> bool:
    """Whether ``query`` reads as search terms rather than a question: it has words, no
    question mark and no English stopword.

    The question mark is what keeps questions in other languages out (the stopword list is
    English only), and the stopwords keep out English questions typed without one.
    """
    found = words(query)
    if not found or any(mark in query for mark in _QUESTION_MARKS):
        return False
    return not any(word in STOPWORDS for word in found)


@dataclass(frozen=True, slots=True)
class FusionWeights:
    """How much the keyword list counts against the vector list (whose weight is 1) in hybrid
    fusion: ``keyword`` for a question, ``keyword_style`` for a keyword-style query."""

    keyword: float = 1.0
    keyword_style: float = 1.0

    @classmethod
    def from_settings(cls, settings: Settings) -> FusionWeights:
        return cls(
            keyword=settings.hybrid_keyword_weight,
            keyword_style=settings.hybrid_keyword_style_weight,
        )

    def keyword_weight(self, query: str) -> float:
        return self.keyword_style if is_keyword_style(query) else self.keyword


@runtime_checkable
class SupportsKeywordSearch(Protocol):
    """A store that can also rank chunks by the words they share with the query."""

    async def keyword_search(
        self,
        query: str,
        vector: Vector,
        k: int,
        tenant: str,
        filters: SearchFilters | None = None,
    ) -> list[Hit]:
        """Up to ``k`` chunks matching ``query``'s words, best keyword match first.

        ``vector`` is the embedded query: each hit is scored by its cosine similarity to it,
        exactly like :meth:`~sift.core.ports.VectorStore.search`, so the two lists' scores mean
        the same thing. ``filters`` narrow the candidates before ``k`` is applied. A store
        whose keyword index is unavailable returns ``[]``.
        """
        ...


def fuse(
    rankings: Sequence[Sequence[Hit]], k: int, weights: Sequence[float] | None = None
) -> list[Hit]:
    """Weighted reciprocal-rank fusion of ``rankings`` into one list of at most ``k`` hits.

    ``weights`` holds one weight per ranking (all 1.0 when omitted). A chunk is identified by
    ``(source_hash, index)``; when it appears in several lists the first list's copy is kept.
    Ties keep first-seen order (Python's sort is stable), so with equal fused scores the earlier
    list wins.
    """
    if weights is None:
        weights = [1.0] * len(rankings)
    scores: dict[tuple[str, int], float] = {}
    hits: dict[tuple[str, int], Hit] = {}
    for ranking, weight in zip(rankings, weights, strict=True):
        for rank, hit in enumerate(ranking, start=1):
            key = (hit.source_hash, hit.index)
            scores[key] = scores.get(key, 0.0) + weight / (RRF_K + rank)
            hits.setdefault(key, hit)
    order = sorted(scores, key=scores.__getitem__, reverse=True)
    return [hits[key] for key in order[:k]]


async def retrieve(
    store: VectorStore,
    query: str,
    vector: Vector,
    k: int,
    tenant: str,
    filters: SearchFilters | None = None,
    *,
    mode: SearchMode,
    weights: FusionWeights = FusionWeights(),  # noqa: B008 (frozen, so sharing one is safe)
) -> list[Hit]:
    """The ``k`` best chunks for ``query`` under ``mode``.

    ``keyword`` returns only keyword matches, possibly none: asked for passages containing these
    words, an empty list is the answer. ``hybrid`` keeps the vector order when nothing matches
    the words, and otherwise fuses the two lists with ``weights`` (plain RRF by default).
    """
    if mode == "vector" or not isinstance(store, SupportsKeywordSearch):
        return await store.search(vector, k, tenant, filters)
    if mode == "keyword":
        return await store.keyword_search(query, vector, k, tenant, filters)
    by_vector = await store.search(vector, k, tenant, filters)
    by_keyword = await store.keyword_search(query, vector, k, tenant, filters)
    if not by_keyword:
        return by_vector
    return fuse([by_vector, by_keyword], k, weights=[1.0, weights.keyword_weight(query)])
