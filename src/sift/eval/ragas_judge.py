"""RAGAS 0.4 collections metrics behind the :class:`~sift.eval.judge.Judge` protocol (D74).

``ragas``, ``openai`` and ``anthropic`` are imported lazily, inside :class:`RagasJudge` only —
they come from the optional ``[eval]`` extra, so the base install, CI, and the frozen engine
bundle never load them. Any OpenAI-compatible endpoint works for both the judge LLM and the
embeddings ``AnswerRelevancy``/``AnswerCorrectness`` need: each gets its own ``AsyncOpenAI``
client at a custom ``base_url``. Claude judges use the native Anthropic SDK instead (D82).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import Any, Literal

from sift.eval.judge import METRICS, JudgeSample

logger = logging.getLogger(__name__)

_INSTALL_HINT = "RAGAS is not installed — run: pip install -e '.[eval]' (or use --skip-judge)"
_JUDGE_MAX_RETRIES = 10
_JUDGE_MAX_TOKENS = 4096


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
        case "answer_recall":
            return {"response": sample.response, "reference": sample.reference or ""}
        case "noise_sensitivity":
            return {
                "user_input": sample.question,
                "response": sample.response,
                "reference": sample.reference or "",
                "retrieved_contexts": contexts,
            }
    raise ValueError(f"unknown metric {metric!r}")


class _ReferenceRecall:
    """Share of the reference's claims the response states: true recall (D84).

    RAGAS's ``FactualCorrectness(mode="recall")`` isn't that. Its numerator counts the
    *response's* claims the reference supports, so a correct answer to a terse reference
    ("Port 502.") scores 0 ÷ 0 → 0 once a strict judge says the bare port number doesn't
    support "FrostyGoop uses port 502". Only the metric's reference-side half is kept here.
    """

    def __init__(self, metric: Any) -> None:
        self._metric = metric

    async def ascore(self, *, response: str, reference: str) -> Any:
        # Private, but pinned by ragas<0.5: decompose the reference, verify each claim (NLI)
        # against the response. No claims → NaN → reported as failed, not as 0.
        verdicts = await self._metric._decompose_and_verify_claims(reference, response)
        value = sum(bool(v) for v in verdicts) / len(verdicts) if len(verdicts) else float("nan")
        return SimpleNamespace(value=value)  # duck-types RAGAS's MetricResult


class _AnchoredNoiseSensitivity:
    """RAGAS ``NoiseSensitivity(mode="relevant")``, the reference read as an answer (D85).

    The score is the share of the response's statements that a *relevant* passage (one
    supporting a reference statement) backs but the reference doesn't. RAGAS writes those
    statements to stand alone, so they restate the question ("In the FrostyGoop Incident,
    attackers cut heating to Ukrainian civilians…"), then checks them against the bare
    reference ("The FrostyGoop Incident (C0041).") — which supports none of the restated
    question: correct, grounded answers scored 1.0, the worst. The premise here is
    ``Question: …\\nAnswer: <reference>``; the arithmetic is RAGAS's.
    """

    def __init__(self, metric: Any) -> None:
        self._metric = metric

    async def ascore(
        self, *, user_input: str, response: str, reference: str, retrieved_contexts: list[str]
    ) -> Any:
        # Private, but pinned by ragas<0.5: statement splitting and per-statement NLI verdicts.
        m = self._metric
        reference_statements = await m._decompose_answer_into_statements(reference, user_input)
        statements = await m._decompose_answer_into_statements(response, user_input)
        if not reference_statements or not statements:
            return SimpleNamespace(value=float("nan"))
        grounded = [False] * len(statements)
        for context in retrieved_contexts:
            if not any(await m._evaluate_statement_faithfulness(reference_statements, context)):
                continue  # an irrelevant passage: what it backs isn't counted
            verdicts = await m._evaluate_statement_faithfulness(statements, context)
            grounded = [g or bool(v) for g, v in zip(grounded, verdicts, strict=True)]
        if not any(grounded):
            return SimpleNamespace(value=0.0)
        premise = f"Question: {user_input}\nAnswer: {reference}"
        correct = await m._evaluate_statement_faithfulness(statements, premise)
        wrong = [g and not c for g, c in zip(grounded, correct, strict=True)]
        return SimpleNamespace(value=sum(wrong) / len(wrong))


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
        provider: Literal["openai", "anthropic"] = "openai",
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
        # on a non-empty one. The SDK's default 2 retries (~1.5 s) can't outlast a hosted judge's
        # per-minute rate-limit window; 10 retries back off for ~1 min (D79). RAGAS's default
        # 1024 output tokens truncates the claim lists of long answers (D80). `Any`:
        # `llm_factory` is typed as the abstract base; `model_args` lives on what it returns.
        llm: Any
        if provider == "anthropic":
            try:
                from anthropic import AsyncAnthropic  # pyright: ignore[reportMissingImports]
            except ImportError as exc:
                raise RuntimeError(_INSTALL_HINT) from exc
            # One EVAL_JUDGE_BASE_URL serves both: the abstention check calls Anthropic's
            # OpenAI-compatible `/v1`, the SDK wants the root and appends `/v1/messages` itself.
            llm = llm_factory(
                model,
                provider="anthropic",
                client=AsyncAnthropic(
                    base_url=base_url.rstrip("/").removesuffix("/v1"),
                    api_key=api_key,
                    max_retries=_JUDGE_MAX_RETRIES,
                ),
                max_tokens=_JUDGE_MAX_TOKENS,
            )
            # Current Claude models reject `temperature` and `top_p` outright (D82).
            llm.model_args.pop("temperature", None)
            llm.model_args.pop("top_p", None)
        else:
            llm = llm_factory(
                model,
                client=AsyncOpenAI(
                    base_url=base_url, api_key=api_key or "none", max_retries=_JUDGE_MAX_RETRIES
                ),
                max_tokens=_JUDGE_MAX_TOKENS,
            )
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
            # Share of the reference's claims the answer covers; extra details don't count
            # (D77). RAGAS's own recall mode doesn't compute that (D84).
            "answer_recall": lambda: _ReferenceRecall(
                collections.FactualCorrectness(llm=llm, mode="recall")
            ),
            "context_utilization": lambda: collections.ContextUtilization(llm=llm),
            # Wrong claims a relevant passage led to; correctness is judged against the
            # question + reference, not the bare reference (D85).
            "noise_sensitivity": lambda: _AnchoredNoiseSensitivity(
                collections.NoiseSensitivity(llm=llm, mode="relevant")
            ),
        }
        # AnswerCorrectness's similarity term (weight 0.25) needs embeddings too; without them
        # its constructor raises, so skip it like answer relevancy instead of crashing the run.
        needs_embeddings = {"answer_relevancy", "answer_correctness"}
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
