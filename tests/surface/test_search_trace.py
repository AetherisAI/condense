"""Unit tests for :meth:`~sift.pipelines.search.SearchPipeline.trace` / ``recap`` (D73).

``trace()`` keeps the intermediates ``search()`` throws away — the raw vector-search order, the
reranked list, the recap's exact context, and per-stage timings — so the eval harness can
measure recall@k beyond FINAL_K and latency per stage without a debug endpoint. ``search()``
must stay ``trace().outcome`` exactly (its own tests in ``test_search_pipeline.py`` are
unchanged).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.llm.null import NullCompleter
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings
from sift.core.types import Chunk, Hit
from sift.pipelines.search import SearchPipeline

MODEL = "bge-m3"
TENANT = "default"
STAGES = {"ensure_ready", "embed", "retrieve", "collapse", "rerank", "recap", "total"}


async def _pipeline(texts: Sequence[str], **overrides: object) -> SearchPipeline:
    embedder = FakeEmbedder()
    store = FakeVectorStore()
    await store.ensure_ready(MODEL, embedder.dim, TENANT)
    chunks = [
        Chunk(text=text, source_path=f"doc{i}.md", page=1, source_hash=f"h{i}", index=0)
        for i, text in enumerate(texts)
    ]
    vectors = await embedder.embed(list(texts))
    await store.upsert([replace(c, vector=v) for c, v in zip(chunks, vectors, strict=True)], TENANT)
    settings = Settings(ingest_token="t", final_k=1, retrieve_k=30, recap_context_k=2)
    settings = settings.model_copy(update=overrides)
    return SearchPipeline(embedder, store, NullReranker(), NullCompleter(), settings)


async def test_trace_keeps_every_stage() -> None:
    pipeline = await _pipeline(["alpha cats", "beta dogs", "gamma birds"])

    trace = await pipeline.trace("beta dogs", TENANT)

    # The raw vector-search list is wider than FINAL_K — exactly what recall@k needs.
    assert len(trace.retrieved) == 3
    assert trace.retrieved[0].source_path == "doc1.md"
    assert [h.source_path for h in trace.ranked] == [h.source_path for h in trace.retrieved]
    # The recap saw ranked[:recap_context_k] — the passages faithfulness is judged against.
    assert trace.context == trace.ranked[:2]
    assert set(trace.timings_ms) == STAGES
    assert all(ms >= 0 for ms in trace.timings_ms.values())
    assert trace.timings_ms["total"] >= trace.timings_ms["embed"]


async def test_search_is_trace_outcome() -> None:
    pipeline = await _pipeline(["alpha cats", "beta dogs"])

    outcome = await pipeline.search("beta dogs", TENANT)
    trace = await pipeline.trace("beta dogs", TENANT)

    assert outcome == trace.outcome


async def test_trace_recap_off_has_no_context() -> None:
    pipeline = await _pipeline(["alpha cats", "beta dogs"])

    trace = await pipeline.trace("beta dogs", TENANT, recap=False)

    assert trace.context == []
    assert trace.outcome.summary == ""


async def test_trace_empty_base() -> None:
    pipeline = await _pipeline([])

    trace = await pipeline.trace("anything", TENANT)

    assert trace.outcome.summary == "No results found."
    assert trace.retrieved == trace.ranked == trace.context == []
    assert {"ensure_ready", "embed", "retrieve", "total"} <= set(trace.timings_ms)


async def test_recap_uses_the_recap_prompt_over_given_passages() -> None:
    pipeline = await _pipeline(["unused"])
    passages = [Hit(text="refunds take two days", score=0.9, source_path="refunds.md", page=3)]

    # NullCompleter echoes the user turn — the same `Question: … Passages: [1] (path p.N)` shape
    # `trace()`'s own recap builds, so a noise sweep over hand-picked passages is apples-to-apples.
    summary = await pipeline.recap("how long do refunds take?", passages)

    assert summary.startswith("Question: how long do refunds take?")
    assert "[1] (refunds.md p.3)\nrefunds take two days" in summary
