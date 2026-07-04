"""Tests for the typed :class:`~sift.config.Settings` — the single source of config values."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sift.config import Settings, get_settings

_ENV_KEYS = (
    "STORE_BACKEND",
    "TURSO_DATABASE_URL",
    "TURSO_AUTH_TOKEN",
    "EMBED_BASE_URL",
    "EMBED_MODEL",
    "EMBED_DIM",
    "EMBED_API_KEY",
    "RERANK_STRATEGY",
    "RERANK_BASE_URL",
    "RERANK_MODEL",
    "RETRIEVE_K",
    "FINAL_K",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "INGEST_TOKEN",
    "EMBED_BATCH_SIZE",
    "EMBED_TIMEOUT_S",
    "EMBED_CONNECT_TIMEOUT_S",
    "OCR_TIMEOUT_S",
    "OCR_CONNECT_TIMEOUT_S",
    "EMBED_RETRY_ATTEMPTS",
    "PARSE_MAX_XLSX_CELLS",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip every config env key so tests see the declared defaults, not the host's env."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_populate() -> None:
    settings = Settings(ingest_token="t")

    assert settings.store_backend == "libsql"
    assert settings.turso_database_url is None
    assert settings.turso_auth_token is None
    assert settings.embed_base_url is None
    assert settings.embed_model == "bge-m3"
    assert settings.embed_dim == 1024
    assert settings.embed_api_key is None
    assert settings.rerank_strategy == "none"
    assert settings.rerank_base_url is None
    assert settings.rerank_model == "bge-reranker-v2-m3"
    assert settings.retrieve_k == 30
    assert settings.final_k == 1
    assert settings.llm_base_url is None
    assert settings.llm_model is None
    assert settings.llm_api_key is None
    assert settings.chunk_size == 512
    assert settings.chunk_overlap == 64
    assert settings.ingest_token == "t"
    # Bounded, config-driven HTTP behaviour for the embed/OCR adapters (replaces old hardcoded
    # module constants: embed batch size 64, a flat 120s timeout).
    assert settings.embed_batch_size == 64
    assert settings.embed_timeout_s == 60.0
    assert settings.embed_connect_timeout_s == 5.0
    assert settings.ocr_timeout_s == 60.0
    assert settings.ocr_connect_timeout_s == 5.0


def test_missing_ingest_token_raises() -> None:
    # ``_env_file=None`` + the cleaned env means no source supplies the required token, so
    # construction must fail. pyright can't see the env source and flags the call — expected.
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_bogus_rerank_strategy_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RERANK_STRATEGY", "bogus")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_embed_retry_attempts_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A 0-attempt budget reached an AssertionError mid-request instead of failing fast at
    # construction (see DECISIONS.md D36) — Field(ge=1) must catch it up front instead.
    monkeypatch.setenv("EMBED_RETRY_ATTEMPTS", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_parse_max_xlsx_cells_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PARSE_MAX_XLSX_CELLS", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_TOKEN", "t")
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
    get_settings.cache_clear()
