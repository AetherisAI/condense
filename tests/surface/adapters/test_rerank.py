"""Tests for the Reranker adapters — the LLM-as-judge double and the HTTP cross-encoder.

``LlmJudgeReranker`` is driven by a fake :class:`~sift.core.ports.Completer` so the index
parsing and reorder are exercised with no model. ``CrossEncoderReranker`` is routed through an
``httpx.MockTransport`` (no network) so the real request/response plumbing is checked against a
canned ``/rerank`` reply that reorders and re-scores the candidates.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable

import httpx
import pytest

from sift.adapters.rerank.crossencoder_http import CrossEncoderReranker
from sift.adapters.rerank.llm_judge import LlmJudgeReranker
from sift.core.types import Hit


def _hit(text: str) -> Hit:
    return Hit(text=text, score=0.0, source_path=f"/docs/{text}.md", page=1)


class _FixedCompleter:
    """Completer double: returns a canned reply and records the (system, user) prompts seen."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._reply


def _patch_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[httpx.Request]:
    """Make every ``httpx.AsyncClient`` use a MockTransport; record the requests it sends."""
    seen: list[httpx.Request] = []

    def _record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(_record)
    real_client = httpx.AsyncClient

    def _make_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _make_client)
    return seen


async def test_llm_judge_puts_chosen_index_first() -> None:
    candidates = [_hit("a"), _hit("b"), _hit("c"), _hit("d")]
    reranker = LlmJudgeReranker(_FixedCompleter("2"))

    out = await reranker.rerank("q", candidates)

    assert [hit.text for hit in out] == ["c", "a", "b", "d"]


async def test_llm_judge_non_numeric_defaults_to_zero() -> None:
    candidates = [_hit("a"), _hit("b"), _hit("c")]
    reranker = LlmJudgeReranker(_FixedCompleter("I cannot decide"))

    out = await reranker.rerank("q", candidates)

    assert [hit.text for hit in out] == ["a", "b", "c"]


async def test_llm_judge_clamps_out_of_range_index() -> None:
    candidates = [_hit("a"), _hit("b"), _hit("c")]
    reranker = LlmJudgeReranker(_FixedCompleter("99"))

    out = await reranker.rerank("q", candidates)

    assert out[0].text == "c"


async def test_llm_judge_only_lists_max_candidates() -> None:
    candidates = [_hit("a"), _hit("b"), _hit("c"), _hit("d")]
    completer = _FixedCompleter("1")
    reranker = LlmJudgeReranker(completer, max_candidates=2)

    out = await reranker.rerank("q", candidates)

    assert [hit.text for hit in out] == ["b", "a", "c", "d"]
    (_system, user) = completer.calls[0]
    assert "/docs/a.md" in user
    assert "/docs/c.md" not in user


async def test_llm_judge_empty_candidates() -> None:
    reranker = LlmJudgeReranker(_FixedCompleter("0"))

    assert await reranker.rerank("q", []) == []


def _ranked(request: httpx.Request) -> httpx.Response:
    # Raw logits, as TEI returns them for ``raw_scores: true`` and llama-server always does.
    return httpx.Response(200, json=[{"index": 1, "score": 2.0}, {"index": 0, "score": -1.0}])


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


async def test_crossencoder_reorders_and_rescores(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ranked)
    reranker = CrossEncoderReranker(base_url="http://tei")
    candidates = [_hit("a"), _hit("b")]

    out = await reranker.rerank("query", candidates)

    assert [hit.text for hit in out] == ["b", "a"]
    assert out[0].score == pytest.approx(_sigmoid(2.0))
    assert out[1].score == pytest.approx(_sigmoid(-1.0))

    (request,) = seen
    assert str(request.url) == "http://tei/rerank"
    assert json.loads(request.content) == {
        "query": "query",
        "texts": ["a", "b"],
        "raw_scores": True,
    }


async def test_crossencoder_scores_are_probabilities_for_large_logits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # llama-server ignores raw_scores and returns logits like 7.8 / -11: the adapter squashes
    # them itself so every backend yields TEI's default 0..1 scale.
    def _extreme(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json=[{"index": 0, "score": 800.0}, {"index": 1, "score": -800.0}]
        )

    _patch_transport(monkeypatch, _extreme)
    out = await CrossEncoderReranker(base_url="http://llama").rerank("q", [_hit("a"), _hit("b")])

    assert out[0].score == pytest.approx(1.0)
    assert out[1].score == pytest.approx(0.0)
    assert all(0.0 <= hit.score <= 1.0 for hit in out)


async def test_crossencoder_unreachable_keeps_retrieval_order(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Nothing listening (the desktop's reranker sidecar not downloaded yet, or crashed): Find
    # keeps working on the vector ranking instead of failing the request.
    def _refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_transport(monkeypatch, _refused)
    candidates = [_hit("a"), _hit("b")]

    with caplog.at_level("WARNING"):
        out = await CrossEncoderReranker(base_url="http://127.0.0.1:8803").rerank("q", candidates)

    assert out == candidates
    assert "unreachable" in caplog.text


async def test_crossencoder_server_error_still_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # A reranker that answers but fails is a real fault, not "not installed": surface it.
    def _boom(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "input is too large"})

    _patch_transport(monkeypatch, _boom)

    with pytest.raises(httpx.HTTPStatusError):
        await CrossEncoderReranker(base_url="http://tei").rerank("q", [_hit("a")])


async def test_crossencoder_empty_candidates_skips_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _ranked)
    reranker = CrossEncoderReranker(base_url="http://tei")

    assert await reranker.rerank("query", []) == []
    assert seen == []


async def test_crossencoder_uses_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    # httpx's 5 s default timed out a CPU TEI scoring 30 full chunks.
    seen = _patch_transport(monkeypatch, _ranked)
    reranker = CrossEncoderReranker(base_url="http://tei", timeout_s=90.0)

    await reranker.rerank("query", [_hit("a"), _hit("b")])

    (request,) = seen
    assert request.extensions["timeout"] == {
        "connect": 90.0,
        "read": 90.0,
        "write": 90.0,
        "pool": 90.0,
    }
