"""Tests for :class:`~sift.adapters.llm.openai_compat.OpenAICompatCompleter`'s
:class:`~sift.core.ports.ToolCompleter` implementation (WP v0.2.0 T3, D40).

No network — every ``httpx.AsyncClient`` is routed through an ``httpx.MockTransport`` (same
pattern as ``test_llm.py``). Covers native tool-calling, the prompted strict-JSON fallback,
the ``auto`` mode's sticky fallback-on-error, and the prompted response parser directly
(pure function, no HTTP at all).
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from sift.adapters.llm.openai_compat import OpenAICompatCompleter, parse_prompted_response

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Semantic search.",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
        },
    }
]


def _patch_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[httpx.Request]:
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


# --- native tool-calling -----------------------------------------------------------------------


def _native_tool_call_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "search",
                                    "arguments": json.dumps({"query": "unity developer CVs"}),
                                },
                            }
                        ],
                    }
                }
            ]
        },
    )


async def test_native_tool_calling_parses_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _native_tool_call_response)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="native")

    result = await completer.complete_with_tools(
        [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}], _TOOLS
    )

    assert result.content is None
    (call,) = result.tool_calls
    assert call.id == "call_1"
    assert call.name == "search"
    assert call.arguments == {"query": "unity developer CVs"}

    (request,) = seen
    body = json.loads(request.content)
    assert body["tools"] == _TOOLS
    assert body["tool_choice"] == "auto"


def _native_final_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": "the answer"}}]}
    )


async def test_native_no_tool_calls_returns_final_content(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, _native_final_response)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="native")

    result = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)

    assert result.tool_calls == ()
    assert result.content == "the answer"


async def test_native_tool_calling_uses_answer_max_tokens_not_recap_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _native_final_response)
    completer = OpenAICompatCompleter(
        "http://llm/v1", "gpt", tool_mode="native", max_tokens=999, answer_max_tokens=42
    )

    await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)

    (request,) = seen
    assert json.loads(request.content)["max_tokens"] == 42  # never the recap's 999


def _native_content_block_list_response(request: httpx.Request) -> httpx.Response:
    """Mistral's actual multi-cited-answer shape: ``content`` is a LIST of content-block dicts,
    ``{"type": "text", ...}`` interleaved with ``{"type": "reference", "reference_ids": [...]}``
    — never a plain string. Reproduces the exact shape from the E2E bug report."""
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Alice fits the XR project"},
                            {"type": "reference", "reference_ids": [3, 7]},
                            {"type": "text", "text": " and so does Bob."},
                        ],
                    }
                }
            ]
        },
    )


async def test_native_content_block_list_normalizes_to_plain_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_transport(monkeypatch, _native_content_block_list_response)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="native")

    result = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)

    assert result.tool_calls == ()
    assert isinstance(result.content, str)
    # Text blocks are concatenated; the reference block never leaks its raw dict shape.
    assert result.content == "Alice fits the XR project and so does Bob."


def _native_stray_tool_json_response(request: httpx.Request) -> httpx.Response:
    """Real-Mistral shape (D42 amendment, D43): a plain string ``content`` — no ``tool_calls``
    field populated at all — that ends with a raw tool-call-args-shaped JSON fragment, as if the
    model started to also emit a call but only ever wrote it as trailing text."""
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            'These platforms support remote onboarding (p.1){"query": '
                            '"remote onboarding platforms", "k": 20}'
                        ),
                    }
                }
            ]
        },
    )


async def test_native_content_with_trailing_tool_json_is_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_transport(monkeypatch, _native_stray_tool_json_response)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="native")

    result = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)

    assert result.tool_calls == ()
    assert result.content == "These platforms support remote onboarding (p.1)"
    assert "{" not in result.content


def _native_content_block_list_with_trailing_tool_json_response(
    request: httpx.Request,
) -> httpx.Response:
    """The two real-Mistral quirks layered together: a content-block LIST (BUG #2) whose final
    text block itself ends with a stray tool-args JSON tail (D42 amendment, D43)."""
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Alice fits the XR project"},
                            {"type": "reference", "reference_ids": [3, 7]},
                            {
                                "type": "text",
                                "text": ' and so does Bob (p.1){"query": "XR project", "k": 20}',
                            },
                        ],
                    }
                }
            ]
        },
    )


async def test_native_content_block_list_with_trailing_tool_json_is_stripped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_transport(monkeypatch, _native_content_block_list_with_trailing_tool_json_response)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="native")

    result = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)

    assert result.tool_calls == ()
    assert result.content == "Alice fits the XR project and so does Bob (p.1)"
    assert "{" not in result.content


async def test_native_mode_forced_never_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "tools not supported"})

    _patch_transport(monkeypatch, _fail)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="native")

    with pytest.raises(httpx.HTTPStatusError):
        await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)


# --- prompted strict-JSON fallback ---------------------------------------------------------


def _prompted_final_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": json.dumps({"final": "the prompted answer"})}}]},
    )


async def test_prompted_mode_sends_no_tools_field(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _prompted_final_response)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="prompted")

    result = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)

    assert result.content == "the prompted answer"
    (request,) = seen
    body = json.loads(request.content)
    assert "tools" not in body
    assert "tool_choice" not in body


async def test_prompted_mode_flattens_tool_role_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _prompted_final_response)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="prompted")

    transcript = [
        {"role": "system", "content": "sys"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "search", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "name": "search", "content": "[]"},
    ]

    await completer.complete_with_tools(transcript, _TOOLS)

    (request,) = seen
    body = json.loads(request.content)
    roles = {m["role"] for m in body["messages"]}
    assert roles <= {"system", "user", "assistant"}  # never a bare "tool" role
    assert all(isinstance(m["content"], str) for m in body["messages"])


# --- auto mode: native attempt, sticky prompted fallback ------------------------------------


async def test_auto_mode_falls_back_to_prompted_on_native_error_and_sticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" in body:
            calls.append("native")
            return httpx.Response(400, json={"error": "tools not supported by this model"})
        calls.append("prompted")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"final": "ok"})}}]},
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="auto")

    first = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert first.content == "ok"
    assert calls == ["native", "prompted"]

    second = await completer.complete_with_tools([{"role": "user", "content": "again"}], _TOOLS)
    assert second.content == "ok"
    # Sticky: the second call never retries the doomed native path.
    assert calls == ["native", "prompted", "prompted"]


# --- parse_prompted_response (pure, no HTTP) -------------------------------------------------


def test_parse_prompted_response_tool_call() -> None:
    completion = parse_prompted_response(json.dumps({"tool": "search", "args": {"query": "x"}}))

    (call,) = completion.tool_calls
    assert call.name == "search"
    assert call.arguments == {"query": "x"}


def test_parse_prompted_response_final() -> None:
    completion = parse_prompted_response(json.dumps({"final": "the answer"}))

    assert completion.tool_calls == ()
    assert completion.content == "the answer"


def test_parse_prompted_response_strips_markdown_fence() -> None:
    fenced = '```json\n{"final": "fenced answer"}\n```'

    completion = parse_prompted_response(fenced)

    assert completion.content == "fenced answer"


def test_parse_prompted_response_tolerates_leading_chatter() -> None:
    noisy = 'Sure, here you go:\n{"final": "chatty answer"}\nHope that helps!'

    completion = parse_prompted_response(noisy)

    assert completion.content == "chatty answer"


def test_parse_prompted_response_falls_back_to_raw_text_on_malformed_json() -> None:
    completion = parse_prompted_response("this is not json at all")

    assert completion.tool_calls == ()
    assert completion.content == "this is not json at all"


def test_parse_prompted_response_strips_trailing_tool_call_json() -> None:
    """D42 amendment, D43: a prompted-mode reply that ignored the ``{"final": ...}`` contract
    and instead wrote its prose answer followed directly by a raw tool-args-shaped JSON
    fragment — the exact shape from the E2E bug report (`...(p.1){"query": "...", "k": 20}`).
    """
    noisy = 'These platforms support remote onboarding (p.1){"query": "remote onboarding", "k": 20}'

    completion = parse_prompted_response(noisy)

    assert completion.tool_calls == ()
    assert completion.content == "These platforms support remote onboarding (p.1)"
    assert "{" not in completion.content


def test_parse_prompted_response_strips_trailing_tool_call_json_with_nested_object() -> None:
    """The trailing JSON tail may itself hold a nested object (e.g. a ``filters`` sub-arg) —
    bracket-matching, not a naive last-``{``/first-``}`` scan, is required to locate the right
    opening brace."""
    noisy = (
        'Bob and Alice both fit.{"query": "XR project", "filters": {"team": "creative"}, "k": 5}'
    )

    completion = parse_prompted_response(noisy)

    assert completion.tool_calls == ()
    assert completion.content == "Bob and Alice both fit."


def test_parse_prompted_response_whole_reply_is_json_without_tool_or_final_key_untouched() -> None:
    """A reply that IS one whole JSON object (no prose before it) is left completely alone even
    without a recognized ``tool``/``final`` key — there is no prose to preserve, and stripping
    would erase the entire answer."""
    whole = json.dumps({"query": "x", "k": 5})

    completion = parse_prompted_response(whole)

    assert completion.tool_calls == ()
    assert completion.content == whole


def test_parse_prompted_response_bad_args_type_degrades_to_empty_dict() -> None:
    completion = parse_prompted_response(json.dumps({"tool": "search", "args": "not-a-dict"}))

    (call,) = completion.tool_calls
    assert call.arguments == {}
