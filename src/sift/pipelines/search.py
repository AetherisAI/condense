"""The search pipeline — embed → retrieve_K → rerank → FINAL_K → recap (README §13).

Ports only (the dependency rule: ``pipelines`` never imports an adapter). It embeds the
query once, retrieves ``RETRIEVE_K`` nearest chunks, reranks them by true relevance, keeps
the ``FINAL_K`` best, and recaps the top passage into a summary carried back with its source
citations. An empty base short-circuits to a "No results found." recap with no sources.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sift.api.schemas import SearchResponse, Source
from sift.config import Settings
from sift.core.ports import Completer, Embedder, Reranker, VectorStore
from sift.core.types import Hit

_RECAP_SYSTEM = (
    "Answer the user's question directly and helpfully, using ONLY the passages provided. Lead "
    "with the answer and draw on whichever passages actually address the question — be clear, "
    "engaged, and define any acronyms.\n"
    "These are constraints on HOW you answer; they must never turn a real answer into a "
    "non-answer:\n"
    "- Use only what the passages state — no outside knowledge, and no hedged guessing ('likely', "
    "'probably', 'may', 'suggests') unless a passage uses those words.\n"
    "- Some of the passages may be about unrelated topics that don't bear on the question. "
    "Silently IGNORE those — do not mention them and do not point out that they're unrelated. "
    "Just answer from the passages that ARE relevant.\n"
    "- Only if NONE of the passages address the question at all, say briefly that the documents "
    "don't cover it, and stop.\n"
    "- Only if the QUESTION itself asserts a relationship or fact the passages don't support "
    "(e.g. 'how does X relate to Y' when nothing connects them) should you push back — say "
    "plainly that the documents don't establish it, rather than inventing a link to satisfy the "
    "question.\n"
    "You may cite the passage(s) you used."
)


def _snippet(text: str, n: int) -> str:
    """Collapse whitespace and truncate ``text`` to ``n`` chars with an ellipsis."""
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= n else collapsed[:n].rstrip() + "…"


def _shingles(text: str, n: int = 5) -> set[str]:
    """Normalised overlapping ``n``-word shingles of ``text`` — the lexical near-dup signal.

    Lowercase + whitespace-collapse, then every window of ``n`` consecutive tokens. Two
    versions of one document share almost all shingles; two genuinely different documents on
    the same topic share few (same words, different sequences). Short texts degrade to a single
    whole-text shingle so they still compare exactly.
    """
    tokens = text.lower().split()
    if len(tokens) < n:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _shingle_similarity(sa: set[str], sb: set[str]) -> float:
    """Jaccard ∈ [0,1] over two pre-built shingle sets — the reusable core of the lexical signal.

    Kept separate from :func:`_shingles` so callers that compare one text against many can build
    each shingle set once and reuse it, instead of re-shingling both sides on every comparison
    (``_collapse_versions`` is O(n²) in comparisons — re-shingling there is quadratic waste).
    """
    if not sa or not sb:
        return 1.0 if sa == sb else 0.0
    return len(sa & sb) / len(sa | sb)


def _lexical_similarity(a: str, b: str) -> float:
    """Token-shingle Jaccard ∈ [0,1]: 1.0 identical text, ~0 disjoint. Order-sensitive, stdlib."""
    return _shingle_similarity(_shingles(a), _shingles(b))


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 ``modified_at`` into a real, comparable ``datetime``.

    ``None`` in, ``None`` out; a value that fails ``datetime.fromisoformat`` also yields ``None``
    (unparseable, treated as absent evidence — never compared as a raw string, A1/A2). A naive
    result (no timezone) is treated as UTC so it stays comparable to an aware one.
    """
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _is_newer(candidate: Hit, kept: Hit) -> bool:
    """True when ``candidate`` is the more recent of two near-duplicates.

    Compares real ``datetime``s parsed from ``modified_at`` (ISO-8601 mtime) — the signal that
    actually distinguishes v1 from v2 regardless of when each was ingested — never raw strings
    (a corrupted value like ``"corrupted-not-a-date"`` must never out-rank a real date, A1). The
    rule, in order:

    1. If either side has a *valid* ``modified_at``, that evidence decides: a side with a valid
       mtime beats a side without one (evidence beats no evidence, A2); if both are valid, the
       later timestamp wins; if both are missing/invalid, fall through.
    2. Only when **neither** side has a valid mtime do we fall back to ``indexed_at``
       (store-local: ISO on libSQL, monotonic counter on the fake), so a pre-metadata corpus
       still degrades gracefully.
    3. When nothing is comparable we keep the incumbent, which holds the better retrieval rank.
    """
    mine_dt, theirs_dt = _parse_datetime(candidate.modified_at), _parse_datetime(kept.modified_at)
    if mine_dt is not None or theirs_dt is not None:
        if mine_dt is None:
            return False
        if theirs_dt is None:
            return True
        return mine_dt > theirs_dt
    mine_idx, theirs_idx = candidate.indexed_at, kept.indexed_at
    if mine_idx is not None and theirs_idx is not None:
        return mine_idx > theirs_idx
    return False


def _collapse_versions(candidates: list[Hit], threshold: float) -> list[Hit]:
    """Fold near-identical passages into one representative, keeping the most recent copy.

    Greedy over the retrieval-ordered candidates: a passage that is lexically ≥ ``threshold``
    similar to one already kept is a version of it — keep whichever was modified more recently
    (see :func:`_is_newer`), in the slot the family already earned. Distinct passages pass
    through untouched, so order and ranking are preserved for everything that is not a duplicate.
    """
    kept: list[Hit] = []
    kept_shingles: list[set[str]] = []  # parallel to `kept`: each keeper's shingle set, built once
    for cand in candidates:
        cand_shingles = _shingles(cand.text)
        dup_index = next(
            (
                i
                for i, ks in enumerate(kept_shingles)
                if _shingle_similarity(cand_shingles, ks) >= threshold
            ),
            None,
        )
        if dup_index is None:
            kept.append(cand)
            kept_shingles.append(cand_shingles)
        elif _is_newer(cand, kept[dup_index]):
            kept[dup_index] = cand
            kept_shingles[dup_index] = cand_shingles
    return kept


def _recap_user(query: str, passages: list[Hit]) -> str:
    """The recap user turn: the question plus the top passages as numbered, cited context."""
    blocks = [
        f"[{i}] ({hit.source_path} p.{hit.page})\n{hit.text}"
        for i, hit in enumerate(passages, start=1)
    ]
    return f"Question: {query}\n\nPassages:\n" + "\n\n".join(blocks)


class SearchPipeline:
    """Wires the four query-time ports together; pins ``(model, dim)`` on first use."""

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        reranker: Reranker,
        completer: Completer,
        settings: Settings,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._reranker = reranker
        self._completer = completer
        self._settings = settings

    async def search(
        self, query: str, tenant: str = "default", recap: bool | None = None
    ) -> SearchResponse:
        settings = self._settings
        await self._store.ensure_ready(settings.embed_model, settings.embed_dim, tenant)
        vectors = await self._embedder.embed([query])
        candidates = await self._store.search(vectors[0], settings.retrieve_k, tenant)
        if not candidates:
            return SearchResponse(summary="No results found.", sources=[])
        # Collapse near-duplicate versions before reranking so a stale copy can never out-rank
        # its newer twin (and so the reranker / recap spend their budget on distinct passages).
        if settings.version_collapse_enabled:
            candidates = _collapse_versions(candidates, settings.version_similarity_threshold)
        ranked = await self._reranker.rerank(query, candidates)
        top = ranked[: settings.final_k]
        # Recap is optional: when off (per-request override, else the config default) we skip the
        # LLM entirely and return just the source citation — the doc + page — as the response.
        do_recap = settings.recap_enabled if recap is None else recap
        if do_recap:
            context = ranked[: settings.recap_context_k]
            summary = await self._completer.complete(_RECAP_SYSTEM, _recap_user(query, context))
        else:
            summary = ""
        sources = [
            Source(
                path=hit.source_path,
                page=hit.page,
                score=hit.score,
                snippet=_snippet(hit.text, settings.source_snippet_chars),
                index=hit.index if hit.index >= 0 else None,
                metadata=hit.metadata,
            )
            for hit in top
        ]
        return SearchResponse(summary=summary, sources=sources)
