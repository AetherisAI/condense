"""First-stage retrieval: vector search, plus keyword search when the store has it, fused.

Embeddings and keywords fail on different questions. Embeddings find a paraphrase that shares
no words with the passage; a keyword index finds the exact identifier, product name or error
code that an embedding blurs into its neighbours. On the MITRE ATT&CK benchmark either one
alone ranks the right document first about 70% of the time, and the two fused 76%.

The lists are merged by reciprocal-rank fusion: each chunk scores ``sum(1 / (RRF_K + rank))``
over the lists it appears in. It uses ranks only, so BM25 scores and cosine similarities never
need to be put on one scale. Each fused hit keeps the cosine similarity its store reported, so
``Hit.score`` still means "how close is this to the query" for every hit; only the order
changes.

Three modes (``SEARCH_MODE``, or per request in the toolbox search): ``hybrid`` fuses both
lists, ``vector`` uses embeddings alone, and ``keyword`` uses the keyword index alone, returning
only passages that contain the query's words (an exact identifier, error code or name). Keyword
search is a capability, like :class:`~sift.pipelines.documents.SupportsDocumentAdmin`: a store
without it serves every mode from vectors alone.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, get_args, runtime_checkable

from sift.config import SearchMode
from sift.core.ports import VectorStore
from sift.core.types import Hit, SearchFilters, Vector

SEARCH_MODES: tuple[SearchMode, ...] = get_args(SearchMode)

# The constant from the paper that introduced RRF (Cormack, Clarke and Buettcher, 2009). It
# flattens the gap between the first few ranks so that neither list's top hit dominates.
RRF_K = 60


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


def fuse(rankings: Sequence[Sequence[Hit]], k: int) -> list[Hit]:
    """Reciprocal-rank fusion of ``rankings`` into one list of at most ``k`` hits.

    A chunk is identified by ``(source_hash, index)``; when it appears in several lists the
    first list's copy is kept. Ties keep first-seen order (Python's sort is stable), so with
    equal fused scores the earlier list wins.
    """
    scores: dict[tuple[str, int], float] = {}
    hits: dict[tuple[str, int], Hit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            key = (hit.source_hash, hit.index)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
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
) -> list[Hit]:
    """The ``k`` best chunks for ``query`` under ``mode``.

    ``keyword`` returns only keyword matches, possibly none: asked for passages containing these
    words, an empty list is the answer. ``hybrid`` keeps the vector order when nothing matches
    the words.
    """
    if mode == "vector" or not isinstance(store, SupportsKeywordSearch):
        return await store.search(vector, k, tenant, filters)
    if mode == "keyword":
        return await store.keyword_search(query, vector, k, tenant, filters)
    by_vector = await store.search(vector, k, tenant, filters)
    by_keyword = await store.keyword_search(query, vector, k, tenant, filters)
    if not by_keyword:
        return by_vector
    return fuse([by_vector, by_keyword], k)
