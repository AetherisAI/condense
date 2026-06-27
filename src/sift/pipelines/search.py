"""The search pipeline — embed → retrieve_K → rerank → FINAL_K → recap (README §13).

Ports only (the dependency rule: ``pipelines`` never imports an adapter). It embeds the
query once, retrieves ``RETRIEVE_K`` nearest chunks, reranks them by true relevance, keeps
the ``FINAL_K`` best, and recaps the top passage into a summary carried back with its source
citations. An empty base short-circuits to a "No results found." recap with no sources.
"""

from __future__ import annotations

from sift.api.schemas import SearchResponse, Source
from sift.config import Settings
from sift.core.ports import Completer, Embedder, Reranker, VectorStore

_RECAP_SYSTEM = (
    "You are a retrieval assistant. Summarize the passage below into a concise recap that "
    "answers the user's query, drawing only on the passage's own content."
)


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

    async def search(self, query: str, tenant: str = "default") -> SearchResponse:
        settings = self._settings
        await self._store.ensure_ready(settings.embed_model, settings.embed_dim, tenant)
        vectors = await self._embedder.embed([query])
        candidates = await self._store.search(vectors[0], settings.retrieve_k, tenant)
        if not candidates:
            return SearchResponse(summary="No results found.", sources=[])
        ranked = await self._reranker.rerank(query, candidates)
        top = ranked[: settings.final_k]
        summary = await self._completer.complete(_RECAP_SYSTEM, top[0].text)
        sources = [Source(path=hit.source_path, page=hit.page, score=hit.score) for hit in top]
        return SearchResponse(summary=summary, sources=sources)
