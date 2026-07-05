"""Typed application configuration — the single source of every value (README §2, §8).

One :class:`Settings`, populated from the environment (or a ``.env``), is the only place
config lives; ``factory.py`` reads it to build the adapters and pipelines. No adapter or
pipeline reaches for ``os.environ`` itself (the config-driven rule). :func:`get_settings`
is the cached accessor the API's dependency layer calls.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """The typed env-config (README §8): field names map case-insensitively to env keys.

    ``ingest_token`` has no default — the upload endpoint must not be unauthenticated, so a
    missing token fails fast at startup rather than silently exposing ``/ingest``.
    """

    store_backend: Literal["libsql", "fake"] = "libsql"
    turso_database_url: str | None = None
    turso_auth_token: str | None = None

    embed_base_url: str | None = None
    embed_model: str = "bge-m3"
    embed_dim: int = 1024
    embed_api_key: str | None = None
    # How many texts go out per embeddings HTTP call (bounds request size/latency; a large
    # document's chunks are split into calls of this size). Was a hardcoded module constant.
    embed_batch_size: int = 64
    # Bounded, independent timeout phases so a dead/unreachable embed backend fails fast rather
    # than tying up a request for the old hardcoded flat 120s: ``embed_connect_timeout_s`` bounds
    # the TCP+TLS handshake (a backend that never answers SYN should fail in seconds, not
    # minutes), ``embed_timeout_s`` bounds the rest (write/read) for a slow-but-connected one.
    embed_timeout_s: float = 60.0
    embed_connect_timeout_s: float = 5.0
    # A backend (e.g. TEI) that free-permit-limits by *input count per request* can 429 a
    # request that is otherwise well-formed — retryable, not a real failure. Bounded retry count
    # for HTTP 429 only (see ``adapters/embedding/openai_compat.py``); backoff is fixed (0.5s/2s/
    # 8s) since only the attempt budget is a plausible per-deployment tuning knob.
    # ge=1: a 0-attempt budget isn't "no retry", it's a config value the embedder's retry loop
    # can't handle (D36 — reached an ``AssertionError`` mid-request instead of failing fast here).
    embed_retry_attempts: int = Field(default=3, ge=1)

    rerank_strategy: Literal["none", "llm", "crossencoder"] = "none"
    rerank_base_url: str | None = None
    rerank_model: str = "bge-reranker-v2-m3"

    retrieve_k: int = 30
    final_k: int = 1
    # Version collapse: before reranking, fold near-identical retrieved passages (a typo fix, a
    # re-export, v1→v2 of the same doc) into one, keeping the most recently *modified* copy (by
    # the source file's mtime) so a stale version can never out-rank its newer twin. Non-
    # destructive (query-time only); off is an exact no-op. Threshold is token-shingle Jaccard
    # ∈ [0,1] (≈0.8 = near-identical text).
    version_collapse_enabled: bool = True
    version_similarity_threshold: float = 0.8
    recap_enabled: bool = True
    recap_context_k: int = 3
    recap_max_tokens: int | None = 512
    recap_temperature: float = 0.3
    source_snippet_chars: int = 300

    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None

    # OCR fallback: when enabled with a base URL, the ingest parser is wrapped so files
    # markitdown can't extract text from (screenshots, scanned PDFs) are OCR'd via Mistral.
    ocr_enabled: bool = False
    ocr_base_url: str = ""
    ocr_model: str = "mistral-ocr-latest"
    ocr_api_key: str = ""
    # Same bounded-timeout rationale as the embedder (see above): a short connect timeout so an
    # unreachable OCR backend fails fast, a longer one for OCR itself (can be genuinely slow).
    ocr_timeout_s: float = 60.0
    ocr_connect_timeout_s: float = 5.0

    # Guard against markitdown's xlsx converter (`pandas.read_excel(engine="openpyxl")`)
    # materializing an implausible sheet: a stray far cell can inflate a sheet's *declared*
    # used-range into the millions of rows even though real content is tiny, which was measured
    # to climb a 38KB file's parse past 2GiB RSS (DECISIONS.md D34). `MarkitdownParser` rejects a
    # sheet whose declared dimension implies more than this many cells with an explicit
    # `ParseError` before ever attempting the conversion.
    # ge=1: a non-positive cell ceiling would reject every sheet unconditionally rather than
    # express "no limit" or any other sane behaviour — fail fast at construction instead (D36).
    parse_max_xlsx_cells: int = Field(default=2_000_000, ge=1)

    chunk_size: int = 512
    chunk_overlap: int = 64
    # Degenerate-chunk floor (DECISIONS.md D50): a fixed-size token window can decode to real-but
    # -useless text when its start happens to land on whitespace/template filler (e.g. a
    # document's padding, a repeated footer) — a handful of characters that still got embedded
    # and surfaced as a search hit. `TokenChunker` drops (never merges) any window whose decoded,
    # whitespace-collapsed text is shorter than this floor.
    # ge=1: a non-positive floor would keep every window unconditionally, i.e. silently disable
    # the guard instead of expressing "no floor" — fail fast at construction instead (D36-style).
    chunk_min_chars: int = Field(default=24, ge=1)

    ingest_token: str

    # Generic production-hardening guardrails (DECISIONS.md D39), independent of the
    # xlsx-specific pre-parse guard above (D34): a post-parse extracted-text ceiling applying to
    # ALL formats (never silent truncation — an oversized `Document` raises an explicit
    # `ParseError` naming the file and both sizes) and a per-file wall-clock timeout wrapping the
    # parse call (`asyncio.wait_for`; a hung/pathologically slow parse fails that one file
    # explicitly instead of stalling the whole ingest batch).
    parse_max_chars: int = Field(default=2_000_000, ge=1)
    parse_timeout_s: float = Field(default=60.0, gt=0)

    # Toolbox `/v1/tools/*` surface (WP v0.2.0 T2, D38): default and hard cap on how many hits
    # `POST /v1/tools/search` returns — a raw-retrieval tool has no recap to bound cost/latency,
    # so the cap (not just the default) is config-driven rather than a hardcoded constant.
    tools_search_k: int = Field(default=8, ge=1)
    tools_search_max_k: int = Field(default=20, ge=1)

    # Per-consumer bearer tokens, additive on top of the required `ingest_token` (D38): parsed
    # from "name1:token1,name2:token2" (see `parse_auth_tokens`). Every token resolves to the
    # same `"default"` tenant today — this exists purely so `resolve_tenant` can log WHICH
    # consumer (WorkyTalky, an MCP client, ...) made a request, ahead of real multi-tenancy.
    auth_tokens: str = ""

    # `/v1/answer` reference agent (WP v0.2.0 T3, D40): `auto` tries native OpenAI-style
    # function-calling once per process and falls back to a prompted strict-JSON ReAct loop on
    # any error, sticking with whichever path worked for the rest of the process's lifetime;
    # `native`/`prompted` force one path with no fallback (debugging/tests). Hard budgets keep a
    # runaway tool loop or a slow model from hanging a request: `answer_max_tool_calls` caps how
    # many tool executions one `/v1/answer` call may make; `answer_timeout_s` is the whole loop's
    # wall-clock ceiling; `answer_max_tokens` bounds the final completion the same way
    # `recap_max_tokens` bounds the recap. Both are graceful-degrade budgets (a best-effort
    # answer + `truncated: true`), never a raw timeout/500 — see `pipelines/answer.py`.
    answer_tool_mode: Literal["auto", "native", "prompted"] = "auto"
    # D40 amendment: 6 -> 10. Observed on the Leitat E2E acceptance pass: a per-document
    # deep-dive strategy (list_documents, then get_document_chunks per candidate) exhausts a
    # budget of 6 well before 14 people are covered, truncating the answer early.
    answer_max_tool_calls: int = Field(default=10, ge=1)
    answer_timeout_s: float = Field(default=120.0, gt=0)
    answer_max_tokens: int | None = 1024
    # Conversation state (store-level turns only — never the product vocabulary D37/D38 forbids):
    # `answer_history_max_turns` caps how many of a conversation's most recent turns are kept
    # (a ring buffer, trimmed on every write — never unbounded growth); `answer_history_ttl_days`
    # is how long an idle conversation survives before it becomes eligible for pruning.
    answer_history_max_turns: int = Field(default=20, ge=1)
    answer_history_ttl_days: int = Field(default=30, ge=1)
    # Auto-title (WP v0.2.0 T6, D42): after the FIRST assistant answer in a conversation, one
    # extra small `Completer.complete()` call (the SAME completer instance already wired for
    # the recap, so it's budget-capped via `recap_max_tokens`/`recap_temperature` — no new
    # knob needed) produces a short title; stored once, never regenerated. Any failure (no
    # completer configured, an HTTP error, ...) falls back to the first user message truncated
    # to 60 chars — never blocks or fails the answer itself.
    answer_autotitle_enabled: bool = True
    # Grounding mode — the trust boundary between the corpus and the model's own training
    # knowledge (D46). Motivating bug: `/v1/answer` always answered from the corpus, EXCEPT it
    # would silently free-generate from the model's own knowledge when a user said "ignore the
    # database" — and that answer was visually indistinguishable from a real, cited one (no
    # citations either way, same card). `"strict"` (default) — corpus-only via tools; abstain
    # honestly when the documents don't cover the question; the system prompt instructs the
    # model to REFUSE an explicit user request to bypass the documents, and the pipeline never
    # reports general-knowledge content as present regardless of what the model returns.
    # `"hybrid"` — may supplement a documented answer with general knowledge, but must label
    # ungrounded content and the pipeline surfaces `from_general_knowledge=True` when it does.
    # `"open"` — an unrestricted general assistant (the old accidental-jailbreak behavior,
    # formalized as an explicit opt-in instead of a silent default). `AnswerRequest.grounding`
    # overrides this per-request; omitted/`None` falls back to this setting.
    answer_grounding_default: Literal["strict", "hybrid", "open"] = "strict"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Build the process-wide settings once and cache them for every later caller."""
    # Every value can arrive from the environment, so the required ``ingest_token`` need not
    # be passed here; the type checker can't see the env source, hence the targeted ignore.
    return Settings()  # pyright: ignore[reportCallIssue]


def _redact(value: str) -> str:
    """First 4 chars + length — enough to spot which entry is malformed in a log line without
    ever printing something that could itself be a bare secret token (D40 amendment: a
    malformed ``auth_tokens`` entry with no ``:`` could BE one, pasted by mistake)."""
    return f"{value[:4]!r}...(len={len(value)})"


def parse_auth_tokens(raw: str) -> dict[str, str]:
    """Parse ``Settings.auth_tokens`` (``"name1:token1,name2:token2"``) into ``{token: name}``.

    Called once at composition-root time (``factory.build_container``), not per-request — so a
    malformed entry logs exactly once per container build, not once per HTTP request. Malformed
    entries (missing ``:``, an empty name, or an empty token) are dropped with a WARNING logging
    only a REDACTED form of the offending entry (never verbatim — a malformed entry with no
    ``:`` could itself be a bare secret token pasted by mistake), never a startup crash: this is
    a convenience layer on top of the hard-required ``ingest_token``, not a replacement for it.
    """
    tokens: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        name, sep, token = entry.partition(":")
        name, token = name.strip(), token.strip()
        if not sep or not name or not token:
            logger.warning("auth_tokens entry malformed, dropping: %s", _redact(entry))
            continue
        tokens[token] = name
    return tokens
