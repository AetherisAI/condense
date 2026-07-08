"""Unit tests for :func:`~sift.factory.build_container` — the single composition root.

With no external base URLs configured the factory must wire the *fake* adapters, so the
container's ``.search`` runs fully offline through ``FakeEmbedder`` + ``FakeVectorStore`` +
``NullReranker``; ``rerank_strategy`` then selects the matching :class:`~sift.core.ports.Reranker`
adapter. No network is touched — the default container is self-contained.
"""

from __future__ import annotations

from sift.adapters.conversation.fake import FakeConversationStore
from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.embedding.openai_compat import OpenAICompatEmbedder
from sift.adapters.llm.null import NullCompleter
from sift.adapters.llm.openai_compat import OpenAICompatCompleter
from sift.adapters.ocr.fallback_parser import OcrFallbackParser
from sift.adapters.ocr.mistral import MistralOcr
from sift.adapters.rerank.crossencoder_http import CrossEncoderReranker
from sift.adapters.rerank.llm_judge import LlmJudgeReranker
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings
from sift.core.hashing import content_hash
from sift.factory import Container, build_container, resolve_chunk_tokenizer
from sift.pipelines.answer import AnswerPipeline
from sift.pipelines.ingest import IngestOutcome, SupportsIngest
from sift.pipelines.tools import ToolRegistry


def test_build_container_defaults_to_fakes() -> None:
    container = build_container(Settings(ingest_token="t"))

    assert isinstance(container, Container)
    assert container.settings.ingest_token == "t"
    # No EMBED/LLM base URL and no Turso URL → the offline fakes, not the HTTP adapters.
    assert isinstance(container.search._embedder, FakeEmbedder)
    assert isinstance(container.search._store, FakeVectorStore)
    assert isinstance(container.search._reranker, NullReranker)
    assert isinstance(container.search._completer, NullCompleter)


async def test_default_container_search_runs_offline() -> None:
    container = build_container(Settings(ingest_token="t"))

    # Empty fake store → the pipeline short-circuits without any network call.
    response = await container.search.search("anything")

    assert response.summary == "No results found."
    assert response.sources == []


def test_rerank_strategy_llm_selects_llm_judge() -> None:
    container = build_container(Settings(ingest_token="t", rerank_strategy="llm"))

    assert isinstance(container.search._reranker, LlmJudgeReranker)


def test_rerank_strategy_crossencoder_selects_crossencoder() -> None:
    container = build_container(
        Settings(
            ingest_token="t",
            rerank_strategy="crossencoder",
            rerank_base_url="http://tei.local",
        )
    )

    assert isinstance(container.search._reranker, CrossEncoderReranker)


def test_build_container_exposes_store_and_ingest() -> None:
    container = build_container(Settings(ingest_token="t"))

    # The same fake store the pipeline searches is also exposed for the ingest/manifest routes.
    assert isinstance(container.store, FakeVectorStore)
    assert container.store is container.search._store
    # A stub ingest stands in until the real IngestPipeline is wired at integration time.
    assert isinstance(container.ingest, SupportsIngest)


def test_embedder_wired_with_configured_batch_size_and_timeouts() -> None:
    settings = Settings(
        ingest_token="t",
        embed_base_url="http://embed.local/v1",
        embed_batch_size=8,
        embed_timeout_s=30.0,
        embed_connect_timeout_s=2.0,
    )

    container = build_container(settings)

    embedder = container.search._embedder
    assert isinstance(embedder, OpenAICompatEmbedder)
    assert embedder._batch_size == 8
    assert embedder._timeout.read == 30.0
    assert embedder._timeout.connect == 2.0


def test_ocr_adapter_wired_with_configured_timeouts(tmp_path) -> None:
    settings = Settings(
        ingest_token="t",
        store_backend="libsql",
        turso_database_url=str(tmp_path / "sift.db"),
        ocr_enabled=True,
        ocr_base_url="http://ocr.local",
        ocr_api_key="k",
        ocr_timeout_s=30.0,
        ocr_connect_timeout_s=2.0,
    )

    container = build_container(settings)

    parser = container.ingest._parser  # type: ignore[attr-defined]
    assert isinstance(parser, OcrFallbackParser)
    ocr = parser._ocr
    assert isinstance(ocr, MistralOcr)
    assert ocr._timeout.read == 30.0
    assert ocr._timeout.connect == 2.0


def test_build_container_wires_tool_registry() -> None:
    container = build_container(Settings(ingest_token="t"))

    assert isinstance(container.tools, ToolRegistry)
    names = {tool.name for tool in container.tools.tools()}
    assert names == {"search", "list_documents", "get_document_chunks"}


def test_build_container_parses_auth_tokens() -> None:
    container = build_container(
        Settings(ingest_token="t", auth_tokens="worktalky:wt-secret,mcp:mcp-secret")
    )

    assert container.auth_tokens == {"wt-secret": "worktalky", "mcp-secret": "mcp"}


def test_build_container_default_auth_tokens_is_empty() -> None:
    container = build_container(Settings(ingest_token="t"))

    assert container.auth_tokens == {}


def test_build_container_wires_answer_pipeline() -> None:
    container = build_container(Settings(ingest_token="t"))

    assert isinstance(container.answer, AnswerPipeline)
    # No LLM_BASE_URL configured -> the completer wired into `search` is the SAME object as the
    # answer loop's ToolCompleter (WP v0.2.0 T3, D40: one adapter, both ports) — never a second.
    assert container.answer._completer is container.search._completer
    assert isinstance(container.answer._completer, NullCompleter)


def test_build_container_answer_uses_configured_tool_mode() -> None:
    container = build_container(
        Settings(
            ingest_token="t",
            llm_base_url="http://llm.local/v1",
            llm_model="gpt",
            answer_tool_mode="prompted",
            answer_max_tokens=256,
            recap_max_tokens=999,
        )
    )

    completer = container.answer._completer
    assert isinstance(completer, OpenAICompatCompleter)
    assert completer._tool_mode == "prompted"
    # Distinct budgets: the answer loop's cap must never be the recap's (WP v0.2.0 T3, D40).
    assert completer._answer_max_tokens == 256
    assert completer._max_tokens == 999


def test_build_container_conversation_store_defaults_to_fake() -> None:
    container = build_container(Settings(ingest_token="t"))

    assert isinstance(container.answer._conversations, FakeConversationStore)


def test_build_container_conversation_store_is_libsql_when_turso_configured(tmp_path) -> None:
    from sift.adapters.conversation.libsql import LibSQLConversationStore

    container = build_container(
        Settings(
            ingest_token="t", store_backend="libsql", turso_database_url=str(tmp_path / "sift.db")
        )
    )

    assert isinstance(container.answer._conversations, LibSQLConversationStore)


def test_build_container_exposes_conversations_same_instance_answer_uses() -> None:
    # WP v0.2.0 T6 (D42): `GET`/`DELETE /v1/conversations*` read the SAME store `answer` writes
    # to, exposed directly on `Container` (mirrors `store`/`ingest` sitting beside `search`).
    container = build_container(Settings(ingest_token="t"))

    assert container.conversations is container.answer._conversations


def test_build_container_wires_title_completer_same_instance_as_recap() -> None:
    # T6 (D42): the auto-title pass reuses the SAME `Completer` instance already wired for the
    # recap — never a second one — so it's budget-capped via the same recap settings.
    container = build_container(Settings(ingest_token="t"))

    assert container.answer._title_completer is container.search._completer


def test_resolve_chunk_tokenizer_auto_picks_bge_m3_for_bge_m3_embed_model() -> None:
    # "auto" (the default) must reproduce the historical hardcoded behavior for the historical
    # default embedding model.
    assert resolve_chunk_tokenizer("auto", "bge-m3") == "bge-m3"


def test_resolve_chunk_tokenizer_auto_matches_bge_m3_case_insensitively_and_as_substring() -> None:
    # A fuller model id (e.g. a namespaced HF repo id) still names bge-m3 — must still match.
    assert resolve_chunk_tokenizer("auto", "BAAI/BGE-M3") == "bge-m3"


def test_resolve_chunk_tokenizer_auto_falls_back_to_tiktoken_for_other_models() -> None:
    # The audit fix: any OTHER EMBED_MODEL must no longer be silently mis-tokenized as bge-m3.
    assert resolve_chunk_tokenizer("auto", "text-embedding-3-small") == "tiktoken"


def test_resolve_chunk_tokenizer_explicit_value_always_wins() -> None:
    # An operator's explicit choice passes through untouched, regardless of EMBED_MODEL.
    assert resolve_chunk_tokenizer("tiktoken", "bge-m3") == "tiktoken"
    assert resolve_chunk_tokenizer("bge-m3", "text-embedding-3-small") == "bge-m3"


async def test_stub_ingest_reports_indexed() -> None:
    container = build_container(Settings(ingest_token="t"))

    outcomes = await container.ingest.ingest([("a.txt", b"hi")], "default")

    assert outcomes == [
        IngestOutcome(
            path="a.txt",
            status="indexed",
            content_hash=content_hash(b"hi"),
            chunks=1,
        )
    ]
