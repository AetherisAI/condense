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

from collections.abc import Sequence
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
from sift.core.hashing import content_hash
from sift.core.ports import Completer, Embedder, Parser, Reranker, VectorStore
from sift.pipelines.ingest import IngestOutcome, IngestPipeline, SupportsIngest
from sift.pipelines.search import SearchPipeline


@dataclass(frozen=True, slots=True, kw_only=True)
class Container:
    """The assembled application: the wired pipeline, its store and ingest, plus the settings.

    ``store`` and ``ingest`` are exposed alongside ``search`` because Dev B's ingest/manifest
    routes need them directly: the manifest reads ``store.known_hashes`` and ``/ingest`` drives
    the ingest seam. They share the same store instance the pipeline searches.
    """

    search: SearchPipeline
    store: VectorStore
    ingest: SupportsIngest
    settings: Settings


class _StubIngest:
    """Placeholder :class:`~sift.pipelines.ingest.SupportsIngest` until the real pipeline lands.

    Reports every file ``indexed`` with its real content-hash and a single chunk, so Dev B's
    ``/ingest`` route is exercisable end-to-end before Arthur's parse/chunk wiring arrives at
    integration time.
    """

    async def ingest(self, files: Sequence[tuple[str, bytes]], tenant: str) -> list[IngestOutcome]:
        return [
            IngestOutcome(path=name, status="indexed", content_hash=content_hash(data), chunks=1)
            for name, data in files
        ]


def build_container(settings: Settings) -> Container:
    """Construct every adapter from ``settings`` and return the wired :class:`Container`."""
    embedder = _build_embedder(settings)
    store = _build_store(settings)
    completer = _build_completer(settings)
    reranker = _build_reranker(settings, completer)
    search = SearchPipeline(embedder, store, reranker, completer, settings)
    ingest = _build_ingest(settings, embedder, store)
    # ``store`` is shared between search, ingest, and the manifest route so a real ingest is
    # immediately searchable and reflected in ``known_hashes``.
    return Container(search=search, store=store, ingest=ingest, settings=settings)


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

        return LibSQLStore(
            settings.turso_database_url, auth_token=settings.turso_auth_token or None
        )
    return FakeVectorStore()


def _build_ingest(settings: Settings, embedder: Embedder, store: VectorStore) -> SupportsIngest:
    """The real :class:`IngestPipeline` when a Turso store is configured, else the stub.

    Parser/chunker (markitdown, tokenizers) are imported lazily inside the real branch so the
    parsing/chunking extras stay out of the default/test path — exactly as the store does. The
    chunker is pinned to the ``bge-m3`` tokenizer to match ``EMBED_MODEL`` (its default is
    ``tiktoken``), and ``(model, dim)`` is threaded so the store pins the tenant on first use.
    """
    if settings.store_backend == "libsql" and settings.turso_database_url:
        from sift.adapters.chunking.token import (  # pyright: ignore[reportMissingImports]
            TokenChunker,
        )
        from sift.adapters.parsing.markitdown import (  # pyright: ignore[reportMissingImports]
            MarkitdownParser,
        )

        parser: Parser = MarkitdownParser()
        # OCR fallback (config-driven): wrap the parser so image/scanned files markitdown can't
        # read are OCR'd via Mistral and indexed — transparent to the ingest pipeline.
        if settings.ocr_enabled and settings.ocr_base_url:
            from sift.adapters.ocr.fallback_parser import OcrFallbackParser
            from sift.adapters.ocr.mistral import MistralOcr

            parser = OcrFallbackParser(
                parser,
                MistralOcr(settings.ocr_base_url, settings.ocr_model, settings.ocr_api_key),
            )

        return IngestPipeline(
            parser,
            TokenChunker(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                tokenizer="bge-m3",
            ),
            embedder,
            store,
            model=settings.embed_model,
            dim=settings.embed_dim,
        )
    return _StubIngest()


def _build_completer(settings: Settings) -> Completer:
    if settings.llm_base_url:
        if not settings.llm_model:
            raise ValueError("LLM_BASE_URL is set but LLM_MODEL is missing")
        return OpenAICompatCompleter(
            settings.llm_base_url,
            settings.llm_model,
            settings.llm_api_key,
            max_tokens=settings.recap_max_tokens,
            temperature=settings.recap_temperature,
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
