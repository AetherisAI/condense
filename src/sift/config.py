"""Typed application configuration — the single source of every value (README §2, §8).

One :class:`Settings`, populated from the environment (or a ``.env``), is the only place
config lives; ``factory.py`` reads it to build the adapters and pipelines. No adapter or
pipeline reaches for ``os.environ`` itself (the config-driven rule). :func:`get_settings`
is the cached accessor the API's dependency layer calls.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

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

    rerank_strategy: Literal["none", "llm", "crossencoder"] = "none"
    rerank_base_url: str | None = None
    rerank_model: str = "bge-reranker-v2-m3"

    retrieve_k: int = 30
    final_k: int = 1
    recap_enabled: bool = True
    recap_context_k: int = 3
    recap_max_tokens: int | None = 512
    recap_temperature: float = 0.3
    source_snippet_chars: int = 300

    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None

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
