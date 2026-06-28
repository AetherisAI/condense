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
from sift.core.types import Hit

_RECAP_SYSTEM = (
    "You are a helpful research assistant. Using ONLY the passages provided, write a clear, "
    "thorough answer to the user's question. Explain it in plain language a non-expert can "
    "follow, and briefly define any technical terms or acronyms you use. Prefer short "
    "paragraphs and bullet points so it is easy to read. If the passages do not fully answer "
    "the question, say what they do and do not cover. Do not invent anything beyond the passages."
)


def _snippet(text: str, n: int) -> str:
    """Collapse whitespace and truncate ``text`` to ``n`` chars with an ellipsis."""
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= n else collapsed[:n].rstrip() + "…"


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
            )
            for hit in top
        ]
        return SearchResponse(summary=summary, sources=sources)
