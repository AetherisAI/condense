"""Typed application configuration — the single source of every value (README §2, §8).

One :class:`Settings`, populated from the environment (or a ``.env``), is the only place
config lives; ``factory.py`` reads it to build the adapters and pipelines. No adapter or
pipeline reaches for ``os.environ`` itself (the config-driven rule). :func:`get_settings`
is the cached accessor the API's dependency layer calls.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    ingest_token: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Build the process-wide settings once and cache them for every later caller."""
    # Every value can arrive from the environment, so the required ``ingest_token`` need not
    # be passed here; the type checker can't see the env source, hence the targeted ignore.
    return Settings()  # pyright: ignore[reportCallIssue]
