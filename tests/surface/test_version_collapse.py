"""Tests for retrieval-time version collapse in :mod:`sift.pipelines.search`.

Two layers: the pure lexical helpers (``_lexical_similarity`` / ``_collapse_versions``) and the
pipeline behaviour (a stale version must never out-rank its newer twin). Fakes only, offline —
``FakeVectorStore`` stamps a monotonic ``indexed_at`` so "newer" is deterministic.
"""

from __future__ import annotations

from dataclasses import replace

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.llm.null import NullCompleter
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings
from sift.core.types import Chunk, Hit
from sift.pipelines.search import (
    SearchPipeline,
    _collapse_versions,
    _is_newer,
    _lexical_similarity,
)

MODEL = "bge-m3"
TENANT = "default"

# A realistic chunk-sized passage and a one-fact edit of it (the refund window changed). At this
# length a single changed token leaves the token-shingle Jaccard well above any sane threshold —
# which is exactly why 0.9 is safe for production-size chunks but would be too strict for toys.
_V1 = (
    "Refund policy. Customers may request a refund within thirty days of purchase for any reason. "
    "Approved refunds are returned to the original payment method and typically settle in five to "
    "seven business days. Refunds on store credit are issued immediately. Shipping fees are "
    "non-refundable except where the return is caused by our own error or a defective product."
)
_V2 = _V1.replace("five to seven business days", "two to three business days")
_DISTINCT = (
    "Vacation policy. Every full-time employee accrues twenty-five paid days of annual leave, "
    "plus public holidays. Unused leave may be carried into the first quarter of the next year. "
    "Requests are approved by the line manager and should be filed at least two weeks in advance."
)


def _hit(
    text: str,
    source_hash: str,
    indexed_at: str,
    score: float,
    modified_at: str | None = None,
) -> Hit:
    return Hit(
        text=text,
        score=score,
        source_path=f"{source_hash}.md",
        page=1,
        source_hash=source_hash,
        index=0,
        modified_at=modified_at,
        indexed_at=indexed_at,
    )


def test_lexical_similarity_separates_versions_from_distinct() -> None:
    assert _lexical_similarity(_V1, _V1) == 1.0
    typo = _V1.replace("defective", "defectiv")  # a single mistyped token
    version_sim = _lexical_similarity(_V1, _V2)  # a sentence-level edit
    distinct_sim = _lexical_similarity(_V1, _DISTINCT)
    # A typo stays near-identical; a real edit on a short doc still clears any sane threshold; an
    # unrelated doc shares almost no 5-word shingles. The gap version≫distinct is the whole point.
    assert _lexical_similarity(_V1, typo) > 0.9
    assert version_sim > 0.6
    assert distinct_sim < 0.1
    assert version_sim > distinct_sim


def test_collapse_keeps_newer_even_when_stale_ranks_first() -> None:
    # The stale copy retrieved first (higher cosine), but the newer copy must win the slot.
    stale = _hit(_V1, "old", indexed_at="001", score=0.99)
    fresh = _hit(_V2, "new", indexed_at="002", score=0.80)
    other = _hit(_DISTINCT, "other", indexed_at="003", score=0.50)

    kept = _collapse_versions([stale, fresh, other], threshold=0.6)

    assert len(kept) == 2  # the two versions folded into one; the distinct doc untouched
    assert kept[0].source_hash == "new"  # newer copy substituted into the family's (best) slot
    assert kept[1].source_hash == "other"


def test_collapse_prefers_real_mtime_over_ingest_order() -> None:
    # The decisive case for true metadata: v2 was ingested FIRST (lower indexed_at) but has the
    # later file mtime. modified_at must win over indexed_at, so the freshest file survives even
    # when ingest order would pick the stale one — exactly the cold-ingest scenario.
    v2 = _hit(_V2, "new", indexed_at="001", modified_at="2026-02-01T00:00:00+00:00", score=0.80)
    v1 = _hit(_V1, "old", indexed_at="002", modified_at="2026-01-01T00:00:00+00:00", score=0.99)

    kept = _collapse_versions([v1, v2], threshold=0.6)

    assert len(kept) == 1
    assert kept[0].source_hash == "new"  # newest by mtime, despite older indexed_at + lower score


def test_is_newer_corrupted_string_loses_to_real_date() -> None:
    """A1/A2 audit finding: ``_is_newer`` used to compare ``modified_at`` as raw strings, so a
    garbage value like 'corrupted-not-a-date' could sort ahead of a real ISO date lexically. A
    corrupted value must never be treated as "newer" than a real, parseable one — in either
    direction."""
    corrupted = _hit(_V1, "old", indexed_at="001", modified_at="corrupted-not-a-date", score=0.99)
    real = _hit(_V2, "new", indexed_at="000", modified_at="2026-01-01T00:00:00+00:00", score=0.10)

    assert _is_newer(corrupted, real) is False  # corrupted candidate never beats a real date
    assert _is_newer(real, corrupted) is True  # a real date always beats a corrupted incumbent


def test_is_newer_known_mtime_beats_unknown_regardless_of_indexed_at() -> None:
    """A2 audit finding: when only one side has a valid ``modified_at``, the old code fell back
    to ``indexed_at`` — so a doc with KNOWN (if old) recency could be evicted by one with
    UNKNOWN recency purely because it was indexed later. Evidence must beat no evidence,
    regardless of indexed_at order."""
    known_old = _hit(
        _V1, "old", indexed_at="001", modified_at="2020-01-01T00:00:00+00:00", score=0.5
    )
    unknown_indexed_later = _hit(_V2, "new", indexed_at="999", modified_at=None, score=0.99)

    assert _is_newer(known_old, unknown_indexed_later) is True
    assert _is_newer(unknown_indexed_later, known_old) is False


def test_is_newer_equal_mtimes_keep_current_tie_behavior() -> None:
    """When both sides carry the identical, valid mtime, the incumbent keeps its slot (the
    candidate must be STRICTLY newer to overtake) — unchanged from before this fix."""
    same = "2026-01-01T00:00:00+00:00"
    a = _hit(_V1, "a", indexed_at="001", modified_at=same, score=0.5)
    b = _hit(_V2, "b", indexed_at="002", modified_at=same, score=0.9)

    assert _is_newer(a, b) is False
    assert _is_newer(b, a) is False


def test_collapse_preserves_distinct_documents() -> None:
    a = _hit(_V1, "a", indexed_at="001", score=0.9)
    b = _hit(_DISTINCT, "b", indexed_at="002", score=0.8)

    kept = _collapse_versions([a, b], threshold=0.6)

    assert [h.source_hash for h in kept] == ["a", "b"]  # nothing collapsed, order preserved


async def _seed(store: FakeVectorStore, embedder: FakeEmbedder, chunks: list[Chunk]) -> None:
    await store.ensure_ready(MODEL, embedder.dim, TENANT)
    for chunk in chunks:  # one upsert per doc so each gets a distinct, increasing recency stamp
        (vector,) = await embedder.embed([chunk.text])
        await store.upsert([replace(chunk, vector=vector)], TENANT)


async def test_pipeline_drops_stale_version_keeps_newest() -> None:
    embedder = FakeEmbedder()
    store = FakeVectorStore()
    # v1 indexed first, v2 (the refund-window edit) indexed second → v2 is newer.
    await _seed(
        store,
        embedder,
        [
            Chunk(text=_V1, source_path="refunds_v1.md", page=1, source_hash="h_old", index=0),
            Chunk(text=_V2, source_path="refunds_v2.md", page=1, source_hash="h_new", index=0),
        ],
    )
    settings = Settings(
        ingest_token="t",
        final_k=5,
        retrieve_k=30,
        recap_enabled=False,
        version_similarity_threshold=0.6,
    )
    pipeline = SearchPipeline(embedder, store, NullReranker(), NullCompleter(), settings)

    response = await pipeline.search(_V2)

    paths = {s.path for s in response.sources}
    assert "refunds_v2.md" in paths  # the newer version survives
    assert "refunds_v1.md" not in paths  # the stale version is collapsed away


async def test_pipeline_keeps_both_when_collapse_disabled() -> None:
    embedder = FakeEmbedder()
    store = FakeVectorStore()
    await _seed(
        store,
        embedder,
        [
            Chunk(text=_V1, source_path="refunds_v1.md", page=1, source_hash="h_old", index=0),
            Chunk(text=_V2, source_path="refunds_v2.md", page=1, source_hash="h_new", index=0),
        ],
    )
    settings = Settings(
        ingest_token="t",
        final_k=5,
        retrieve_k=30,
        recap_enabled=False,
        version_collapse_enabled=False,
    )
    pipeline = SearchPipeline(embedder, store, NullReranker(), NullCompleter(), settings)

    response = await pipeline.search(_V2)

    paths = {s.path for s in response.sources}
    assert {"refunds_v1.md", "refunds_v2.md"} <= paths  # off → both versions returned (no-op)
