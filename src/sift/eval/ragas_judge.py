"""RAGAS 0.4 collections metrics behind the :class:`~sift.eval.judge.Judge` protocol (D74).

``ragas`` and ``openai`` are imported lazily, inside :class:`RagasJudge` only — they come from
the optional ``[eval]`` extra, so the base install, CI, and the frozen engine bundle never load
them. Any OpenAI-compatible endpoint works for both the judge LLM and the embeddings
``AnswerRelevancy``/``AnswerCorrectness`` need: each gets its own ``AsyncOpenAI`` client at a
custom ``base_url``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from sift.eval.judge import METRICS, JudgeSample

logger = logging.getLogger(__name__)

_INSTALL_HINT = "RAGAS is not installed — run: pip install -e '.[eval]' (or use --skip-judge)"


def _metric_kwargs(metric: str, sample: JudgeSample) -> dict[str, Any]:
    """The exact ``ascore`` keyword arguments each collections metric takes (ragas 0.4.3)."""
    contexts = list(sample.contexts)
    match metric:
        case "answer_relevancy":
            return {"user_input": sample.question, "response": sample.response}
        case "faithfulness" | "context_utilization":
            return {
                "user_input": sample.question,
                "response": sample.response,
                "retrieved_contexts": contexts,
            }
        case "answer_correctness":
            return {
                "user_input": sample.question,
                "response": sample.response,
                "reference": sample.reference or "",
            }
        case "noise_sensitivity":
            return {
                "user_input": sample.question,
                "response": sample.response,
                "reference": sample.reference or "",
                "retrieved_contexts": contexts,
            }
    raise ValueError(f"unknown metric {metric!r}")


class RagasJudge:
    """Scores one sample × metric with RAGAS; a failed metric is ``None``, never an exception."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        embed_base_url: str,
        embed_model: str,
        embed_api_key: str,
        metrics: Sequence[str] = METRICS,
    ) -> None:
        try:
            import ragas  # pyright: ignore[reportMissingImports]
            from openai import AsyncOpenAI  # pyright: ignore[reportMissingImports]
            from ragas.embeddings.base import (  # pyright: ignore[reportMissingImports]
                embedding_factory,
            )
            from ragas.llms import llm_factory  # pyright: ignore[reportMissingImports]
            from ragas.metrics import collections  # pyright: ignore[reportMissingImports]
        except ImportError as exc:
            raise RuntimeError(_INSTALL_HINT) from exc
        if not base_url or not model:
            raise RuntimeError(
                "no judge LLM configured — set EVAL_JUDGE_BASE_URL/EVAL_JUDGE_MODEL (or LLM_*), "
                "or use --skip-judge"
            )
        # Local OpenAI-compatible servers (Ollama, llama.cpp) take any key; the client insists
        # on a non-empty one.
        llm = llm_factory(model, client=AsyncOpenAI(base_url=base_url, api_key=api_key or "none"))
        # `Any`: ragas's own embedding unions don't line up with each metric's parameter type,
        # and in CI (no [eval] extra) these names don't resolve at all.
        embeddings: Any = None
        if embed_base_url:
            embeddings = embedding_factory(
                "openai",
                model=embed_model,
                client=AsyncOpenAI(base_url=embed_base_url, api_key=embed_api_key or "none"),
            )
        builders: dict[str, Callable[[], Any]] = {
            "answer_relevancy": lambda: collections.AnswerRelevancy(llm=llm, embeddings=embeddings),
            "faithfulness": lambda: collections.Faithfulness(llm=llm),
            "answer_correctness": lambda: collections.AnswerCorrectness(
                llm=llm, embeddings=embeddings
            ),
            "context_utilization": lambda: collections.ContextUtilization(llm=llm),
            "noise_sensitivity": lambda: collections.NoiseSensitivity(llm=llm, mode="relevant"),
        }
        needs_embeddings = {"answer_relevancy"}
        self._metrics: dict[str, Any] = {}
        for metric in metrics:
            if metric in needs_embeddings and embeddings is None:
                logger.warning("no embeddings endpoint configured — skipping %s", metric)
                continue
            self._metrics[metric] = builders[metric]()
        self._name = f"ragas {ragas.__version__} · {model}"

    @property
    def name(self) -> str:
        return self._name

    async def score(self, sample: JudgeSample, metric: str) -> float | None:
        scorer = self._metrics.get(metric)
        if scorer is None:
            return None
        try:
            result = await scorer.ascore(**_metric_kwargs(metric, sample))
            value = float(result.value)
        except Exception as exc:  # noqa: BLE001 — judge failures are reported, not fatal
            logger.warning("%s failed: %s: %s", metric, type(exc).__name__, exc)
            return None
        return value if value == value else None  # NaN → None
