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


async def test_null_completer_echoes_user() -> None:
    completer = NullCompleter()

    assert await completer.complete("any system prompt", "the user turn") == "the user turn"
