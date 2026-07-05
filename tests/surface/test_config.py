"""Tests for the typed :class:`~sift.config.Settings` — the single source of config values."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sift.config import Settings, get_settings, parse_auth_tokens

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
    "PARSE_MAX_CHARS",
    "PARSE_TIMEOUT_S",
    "TOOLS_SEARCH_K",
    "TOOLS_SEARCH_MAX_K",
    "AUTH_TOKENS",
    "ANSWER_TOOL_MODE",
    "ANSWER_MAX_TOOL_CALLS",
    "ANSWER_TIMEOUT_S",
    "ANSWER_MAX_TOKENS",
    "ANSWER_HISTORY_MAX_TURNS",
    "ANSWER_HISTORY_TTL_DAYS",
    "ANSWER_GROUNDING_DEFAULT",
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
    # Generic post-parse guardrails (D39): text ceiling + per-file wall-clock timeout, applied
    # to every format regardless of the xlsx-specific pre-parse guard (D34) above.
    assert settings.parse_max_chars == 2_000_000
    assert settings.parse_timeout_s == 60.0
    # Toolbox `/v1/tools/*` surface (WP v0.2.0 T2, D38).
    assert settings.tools_search_k == 8
    assert settings.tools_search_max_k == 20
    assert settings.auth_tokens == ""
    # `/v1/answer` reference agent (WP v0.2.0 T3, D40).
    assert settings.answer_tool_mode == "auto"
    # D40 amendment: 6 -> 10 (observed: a per-document deep-dive strategy exhausts 6 on ~14
    # people, truncating before the model can enumerate them all).
    assert settings.answer_max_tool_calls == 10
    assert settings.answer_timeout_s == 120.0
    assert settings.answer_max_tokens == 1024
    assert settings.answer_history_max_turns == 20
    assert settings.answer_history_ttl_days == 30
    # Grounding mode (D46): defaults to the safest, corpus-only trust boundary.
    assert settings.answer_grounding_default == "strict"


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


def test_parse_max_chars_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A non-positive ceiling would reject every parse unconditionally — never an intended
    # configuration (D39, same rationale as D36's `parse_max_xlsx_cells` guard).
    monkeypatch.setenv("PARSE_MAX_CHARS", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_parse_timeout_s_non_positive_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A zero/negative timeout would fail every parse immediately (or is meaningless to
    # `asyncio.wait_for`) — fail fast and legibly at construction instead (D39).
    monkeypatch.setenv("PARSE_TIMEOUT_S", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_TOKEN", "t")
    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
    get_settings.cache_clear()


def test_tools_search_k_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOOLS_SEARCH_K", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_tools_search_max_k_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOOLS_SEARCH_MAX_K", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


# --- /v1/answer reference agent (WP v0.2.0 T3, D40) ------------------------------------


def test_bogus_answer_tool_mode_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANSWER_TOOL_MODE", "bogus")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_answer_grounding_default_accepts_hybrid_and_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANSWER_GROUNDING_DEFAULT", "hybrid")
    assert Settings(ingest_token="t").answer_grounding_default == "hybrid"
    monkeypatch.setenv("ANSWER_GROUNDING_DEFAULT", "open")
    assert Settings(ingest_token="t").answer_grounding_default == "open"


def test_bogus_answer_grounding_default_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANSWER_GROUNDING_DEFAULT", "bogus")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_answer_max_tool_calls_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An unbounded/zero tool-call budget defeats the whole point of the budget (D40).
    monkeypatch.setenv("ANSWER_MAX_TOOL_CALLS", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_answer_timeout_s_non_positive_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_TIMEOUT_S", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_answer_history_max_turns_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_HISTORY_MAX_TURNS", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


def test_answer_history_ttl_days_below_one_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANSWER_HISTORY_TTL_DAYS", "0")
    with pytest.raises(ValidationError):
        Settings(ingest_token="t")


# --- parse_auth_tokens (WP v0.2.0 T2, D38) ---------------------------------------------


def test_parse_auth_tokens_empty_string_is_empty_dict() -> None:
    assert parse_auth_tokens("") == {}


def test_parse_auth_tokens_parses_name_token_pairs() -> None:
    assert parse_auth_tokens("worktalky:wt-secret,mcp:mcp-secret") == {
        "wt-secret": "worktalky",
        "mcp-secret": "mcp",
    }


def test_parse_auth_tokens_tolerates_whitespace() -> None:
    assert parse_auth_tokens(" worktalky : wt-secret , mcp:mcp-secret ") == {
        "wt-secret": "worktalky",
        "mcp-secret": "mcp",
    }


def test_parse_auth_tokens_drops_malformed_entries(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        parsed = parse_auth_tokens("good:tok, missing-colon, empty-name:, :empty-token,")

    assert parsed == {"tok": "good"}
    assert "malformed" in caplog.text.lower()


def test_parse_auth_tokens_malformed_entry_logged_redacted_not_verbatim(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # D40 amendment: a malformed entry (no ":") could actually BE a bare secret token pasted by
    # mistake — logging it verbatim would leak it into logs. Only a redacted form (first 4
    # chars + length) may ever appear.
    secret = "supersecrettoken12345"
    with caplog.at_level("WARNING"):
        parse_auth_tokens(f"good:tok,{secret}")

    assert secret not in caplog.text
    assert secret[:4] in caplog.text
    assert str(len(secret)) in caplog.text
