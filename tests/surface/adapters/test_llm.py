"""Tests for the Completer adapters — the OpenAI-compatible chat client and the null double.

No network: ``OpenAICompatCompleter`` is routed through an ``httpx.MockTransport`` so the real
request/response plumbing (headers, JSON, ``raise_for_status``) is exercised against a canned
``/chat/completions`` reply. ``NullCompleter`` needs no transport — it just echoes the user turn.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from sift.adapters.llm.null import NullCompleter
from sift.adapters.llm.openai_compat import OpenAICompatCompleter


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


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": "the recap"}}]}
    )


async def test_complete_reads_choice_message_content(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    completer = OpenAICompatCompleter(base_url="http://llm/v1", model="gpt", api_key="secret")

    out = await completer.complete("be brief", "summarize this")

    assert out == "the recap"

    (request,) = seen
    assert str(request.url) == "http://llm/v1/chat/completions"
    assert json.loads(request.content) == {
        "model": "gpt",
        "messages": [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "summarize this"},
        ],
    }
    assert request.headers["authorization"] == "Bearer secret"


async def test_no_api_key_omits_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    completer = OpenAICompatCompleter(base_url="http://llm/v1", model="gpt")

    await completer.complete("sys", "usr")

    (request,) = seen
    assert "authorization" not in request.headers


async def test_generation_params_included_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    completer = OpenAICompatCompleter(
        base_url="http://llm/v1", model="gpt", max_tokens=256, temperature=0.2
    )

    await completer.complete("sys", "usr")

    (request,) = seen
    body = json.loads(request.content)
    assert body["max_tokens"] == 256
    assert body["temperature"] == 0.2


async def test_generation_params_omitted_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    completer = OpenAICompatCompleter(base_url="http://llm/v1", model="gpt")

    await completer.complete("sys", "usr")

    (request,) = seen
    body = json.loads(request.content)
    assert "max_tokens" not in body
    assert "temperature" not in body


def _no_wait(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Skip the retry backoff's real sleep; record each requested delay."""
    delays: list[float] = []

    async def _sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("sift.adapters.llm.openai_compat._sleep", _sleep)
    return delays


async def test_rate_limit_is_retried_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter([429, 503, 200])

    def _flaky(request: httpx.Request) -> httpx.Response:
        status = next(replies)
        return _ok(request) if status == 200 else httpx.Response(status, json={"error": "busy"})

    seen = _patch_transport(monkeypatch, _flaky)
    delays = _no_wait(monkeypatch)
    completer = OpenAICompatCompleter(base_url="http://llm/v1", model="gpt")

    assert await completer.complete("sys", "usr") == "the recap"
    assert len(seen) == 3
    assert delays == [2.0, 4.0]


async def test_retry_after_header_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = iter([httpx.Response(429, headers={"retry-after": "7"}), None])

    def _limited(request: httpx.Request) -> httpx.Response:
        return next(replies) or _ok(request)

    _patch_transport(monkeypatch, _limited)
    delays = _no_wait(monkeypatch)
    completer = OpenAICompatCompleter(base_url="http://llm/v1", model="gpt")

    await completer.complete("sys", "usr")

    assert delays == [7.0]


async def test_retries_give_up_after_max(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, lambda _r: httpx.Response(429, json={"error": "slow"}))
    _no_wait(monkeypatch)
    completer = OpenAICompatCompleter(base_url="http://llm/v1", model="gpt", max_retries=2)

    with pytest.raises(httpx.HTTPStatusError):
        await completer.complete("sys", "usr")
    assert len(seen) == 3  # the first attempt + 2 retries


async def test_server_error_500_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 500 can mean "tools not supported" — auto mode must see it at once."""
    seen = _patch_transport(monkeypatch, lambda _r: httpx.Response(500, json={"error": "no"}))
    delays = _no_wait(monkeypatch)
    completer = OpenAICompatCompleter(base_url="http://llm/v1", model="gpt")

    with pytest.raises(httpx.HTTPStatusError):
        await completer.complete("sys", "usr")
    assert len(seen) == 1
    assert delays == []


async def test_null_completer_echoes_user() -> None:
    completer = NullCompleter()

    assert await completer.complete("any system prompt", "the user turn") == "the user turn"
