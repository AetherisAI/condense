"""``EvalSettings`` — the harness's own typed config (``EVAL_*`` keys, same ``.env``) (D73).

Kept apart from the app's :class:`~sift.config.Settings` on purpose: these are not server
runtime knobs, so they stay out of the api container's env contract (and out of
``test_config_env_parity.py``). The system under test is still configured by ``Settings``
exactly as the server would be — the eval reads the same ``.env``.

Judge and judge-embedding endpoints fall back to the app's own ``LLM_*`` / ``EMBED_*`` values, so
a zero-config run works; point ``EVAL_JUDGE_*`` at a stronger model than the generator for
trustworthy scores (a model grading itself is biased — the report warns when they're the same).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from sift.config import Settings

# Never used to serve anything — the eval doesn't start the API — but `Settings` requires an
# ingest token, so a `.env` written only for evaluation still loads.
_PLACEHOLDER_INGEST_TOKEN = "unused-by-sift-eval"


def _floats(raw: str) -> list[float]:
    values = [float(part) for part in raw.split(",") if part.strip()]
    if not values:
        raise ValueError("must list at least one value")
    return values


def _ints(raw: str) -> list[int]:
    values = _floats(raw)
    if any(v != int(v) for v in values):
        raise ValueError(f"expected whole numbers, got {raw!r}")
    return [int(v) for v in values]


class EvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVAL_", env_file=".env", extra="ignore")

    judge_base_url: str = ""
    judge_model: str = ""
    judge_api_key: str = ""
    # "anthropic": RAGAS drives Claude through the native SDK, with no sampling params (D82).
    judge_provider: Literal["openai", "anthropic"] = "openai"
    judge_concurrency: int = Field(default=4, ge=1)
    embed_base_url: str = ""
    embed_model: str = ""
    embed_api_key: str = ""

    k_values: str = "1,3,5,10"
    evidence_match_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    noise_ratios: str = "0,0.25,0.5,0.75"
    noise_context_size: int = Field(default=4, ge=1)
    ask_max_contexts: int = Field(default=20, ge=1)
    bootstrap_min_chars: int = Field(default=200, ge=1)
    grounding: Literal["strict", "hybrid", "open"] = "strict"
    strip_citations: bool = True
    warmup: int = Field(default=1, ge=0)
    seed: int = 13
    tenant: str = "default"
    output_dir: str = "eval-runs"

    @field_validator("k_values")
    @classmethod
    def _check_ks(cls, raw: str) -> str:
        if any(k < 1 for k in _ints(raw)):
            raise ValueError("every k must be >= 1")
        return raw

    @field_validator("noise_ratios")
    @classmethod
    def _check_ratios(cls, raw: str) -> str:
        if any(not 0.0 <= r < 1.0 for r in _floats(raw)):
            raise ValueError("every noise ratio must be in [0, 1)")
        return raw

    @property
    def ks(self) -> list[int]:
        return sorted(set(_ints(self.k_values)))

    @property
    def ratios(self) -> list[float]:
        return sorted(set(_floats(self.noise_ratios)))

    def judge_settings(self, app: Settings) -> Settings:
        """``app`` with ``LLM_*`` swapped for the judge's — the input to ``build_completer``."""
        update: dict[str, Any] = {
            "llm_base_url": self.judge_base_url or app.llm_base_url,
            "llm_model": self.judge_model or app.llm_model,
            "llm_api_key": self.judge_api_key or app.llm_api_key,
        }
        if self.judge_provider == "anthropic":
            # The completer reuses the recap's temperature, which Claude rejects (D81, D82).
            update["recap_temperature"] = None
        return app.model_copy(update=update)

    def judge_model_name(self, app: Settings) -> str:
        return self.judge_model or app.llm_model or ""

    def judge_embed(self, app: Settings) -> tuple[str, str, str]:
        """``(base_url, model, api_key)`` for RAGAS's embeddings, defaulting to the app's own."""
        return (
            self.embed_base_url or app.embed_base_url or "",
            self.embed_model or app.embed_model,
            self.embed_api_key or app.embed_api_key or "",
        )


def load_settings(env_file: Path | None = None) -> tuple[Settings, EvalSettings]:
    """The app's ``Settings`` and the ``EvalSettings``, from ``env_file`` (else ``.env``)."""
    # Only override `_env_file` when one was asked for — otherwise each model's own
    # `model_config["env_file"]` applies (which tests neutralize to stay hermetic).
    source: dict[str, Any] = {"_env_file": str(env_file)} if env_file else {}
    try:
        app = Settings(**source)
    except ValidationError as exc:
        if [e["loc"] for e in exc.errors()] != [("ingest_token",)]:
            raise
        app = Settings(**source, ingest_token=_PLACEHOLDER_INGEST_TOKEN)
    return app, EvalSettings(**source)
