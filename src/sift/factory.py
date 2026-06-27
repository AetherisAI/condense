"""The composition root — the ONE place adapters are constructed (README §2, P2).

``factory.py`` reads the typed :class:`~sift.config.Settings` and assembles the concrete
adapters behind the ports, then wires them into the query-time :class:`SearchPipeline`. It is
the only module allowed to import adapters *and* know which one to pick; everything else
codes against the ports. Each selection follows the config-driven rule: a configured base URL
turns on the real HTTP adapter, its absence falls back to the offline fake/null so the whole
container runs self-contained in tests with no network and no heavy extras.

The libSQL store is imported lazily inside its branch (and only when a Turso URL is actually
configured) so the default/test path never needs the ``libsql`` extra installed.
"""

from __future__ import annotations

from dataclasses import dataclass

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.embedding.openai_compat import OpenAICompatEmbedder
from sift.adapters.llm.null import NullCompleter
from sift.adapters.llm.openai_compat import OpenAICompatCompleter
from sift.adapters.rerank.crossencoder_http import CrossEncoderReranker
from sift.adapters.rerank.llm_judge import LlmJudgeReranker
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings
from sift.core.ports import Completer, Embedder, Reranker, VectorStore
from sift.pipelines.search import SearchPipeline


@dataclass(frozen=True, slots=True, kw_only=True)
class Container:
    """The assembled application: the wired pipeline plus the settings it was built from."""

    search: SearchPipeline
    settings: Settings


def build_container(settings: Settings) -> Container:
    """Construct every adapter from ``settings`` and return the wired :class:`Container`."""
    embedder = _build_embedder(settings)
    store = _build_store(settings)
    completer = _build_completer(settings)
    reranker = _build_reranker(settings, completer)
    search = SearchPipeline(embedder, store, reranker, completer, settings)
    return Container(search=search, settings=settings)


def _build_embedder(settings: Settings) -> Embedder:
    if settings.embed_base_url:
        return OpenAICompatEmbedder(
            settings.embed_base_url,
            settings.embed_model,
            settings.embed_api_key,
            settings.embed_dim,
        )
    return FakeEmbedder(settings.embed_dim)


def _build_store(settings: Settings) -> VectorStore:
    if settings.store_backend == "libsql" and settings.turso_database_url:
        # Lazy: the ``libsql`` extra stays out of the default/test path (it is only needed
        # when a real Turso database is configured), so it need not be installed otherwise.
        from sift.adapters.store.libsql import (  # pyright: ignore[reportMissingImports]
            LibSQLStore,
        )

        return LibSQLStore(settings.turso_database_url, auth_token=settings.turso_auth_token)
    return FakeVectorStore()


def _build_completer(settings: Settings) -> Completer:
    if settings.llm_base_url:
        if not settings.llm_model:
            raise ValueError("LLM_BASE_URL is set but LLM_MODEL is missing")
        return OpenAICompatCompleter(
            settings.llm_base_url, settings.llm_model, settings.llm_api_key
        )
    return NullCompleter()


def _build_reranker(settings: Settings, completer: Completer) -> Reranker:
    match settings.rerank_strategy:
        case "llm":
            return LlmJudgeReranker(completer)
        case "crossencoder":
            if not settings.rerank_base_url:
                raise ValueError("RERANK_STRATEGY='crossencoder' requires RERANK_BASE_URL")
            return CrossEncoderReranker(settings.rerank_base_url, settings.rerank_model)
        case "none":
            return NullReranker()
