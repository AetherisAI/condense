"""Tests for :class:`~sift.adapters.llm.openai_compat.OpenAICompatCompleter`'s
:class:`~sift.core.ports.ToolCompleter` implementation (WP v0.2.0 T3, D40).

No network — every ``httpx.AsyncClient`` is routed through an ``httpx.MockTransport`` (same
pattern as ``test_llm.py``). Covers native tool-calling, the prompted strict-JSON fallback,
the ``auto`` mode's sticky fallback-on-error, and the prompted response parser directly
(pure function, no HTTP at all).
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable

import httpx
import pytest

from sift.adapters.llm.openai_compat import (
    OpenAICompatCompleter,
    _is_retryable_error,
    parse_prompted_response,
)
from sift.core.toolprotocol import scan_protocol_objects

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

# The ``known_tools`` every pure ``parse_prompted_response`` test below passes — mirrors _TOOLS'
# one registered name (postmortem follow-up audit, D8: the parser now only recognizes a
# ``{"tool": ...}`` object naming a REGISTERED tool as a real call).
_KNOWN_TOOLS = frozenset({"search"})


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
    completion = parse_prompted_response(
        json.dumps({"tool": "search", "args": {"query": "x"}}), known_tools=_KNOWN_TOOLS
    )

    (call,) = completion.tool_calls
    assert call.name == "search"
    assert call.arguments == {"query": "x"}


def test_parse_prompted_response_final() -> None:
    completion = parse_prompted_response(
        json.dumps({"final": "the answer"}), known_tools=_KNOWN_TOOLS
    )

    assert completion.tool_calls == ()
    assert completion.content == "the answer"


def test_parse_prompted_response_strips_markdown_fence() -> None:
    fenced = '```json\n{"final": "fenced answer"}\n```'

    completion = parse_prompted_response(fenced, known_tools=_KNOWN_TOOLS)

    assert completion.content == "fenced answer"


def test_parse_prompted_response_tolerates_leading_chatter() -> None:
    noisy = 'Sure, here you go:\n{"final": "chatty answer"}\nHope that helps!'

    completion = parse_prompted_response(noisy, known_tools=_KNOWN_TOOLS)

    assert completion.content == "chatty answer"


def test_parse_prompted_response_falls_back_to_raw_text_on_malformed_json() -> None:
    completion = parse_prompted_response("this is not json at all", known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()
    assert completion.content == "this is not json at all"


def test_parse_prompted_response_strips_trailing_tool_call_json() -> None:
    """D42 amendment, D43: a prompted-mode reply that ignored the ``{"final": ...}`` contract
    and instead wrote its prose answer followed directly by a raw tool-args-shaped JSON
    fragment — the exact shape from the E2E bug report (`...(p.1){"query": "...", "k": 20}`).
    """
    noisy = 'These platforms support remote onboarding (p.1){"query": "remote onboarding", "k": 20}'

    completion = parse_prompted_response(noisy, known_tools=_KNOWN_TOOLS)

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

    completion = parse_prompted_response(noisy, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()
    assert completion.content == "Bob and Alice both fit."


def test_parse_prompted_response_whole_reply_is_json_without_tool_or_final_key_untouched() -> None:
    """A reply that IS one whole JSON object (no prose before it) is left completely alone even
    without a recognized ``tool``/``final`` key — there is no prose to preserve, and stripping
    would erase the entire answer."""
    whole = json.dumps({"query": "x", "k": 5})

    completion = parse_prompted_response(whole, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()
    assert completion.content == whole


def test_parse_prompted_response_bad_args_type_degrades_to_empty_dict() -> None:
    completion = parse_prompted_response(
        json.dumps({"tool": "search", "args": "not-a-dict"}), known_tools=_KNOWN_TOOLS
    )

    (call,) = completion.tool_calls
    assert call.arguments == {}


# --- D73: batched multi-tool-call prompted replies (2026-08-18 live-demo postmortem) ---------


def test_parse_prompted_response_two_tool_calls_on_separate_lines_batches_both() -> None:
    """The exact FAILURE A shape: a two-part question makes the model emit TWO tool-call JSON
    objects, one per line, instead of the one the strict-JSON contract allowed. Both must be
    parsed into real tool calls (executed in the same turn), not leaked as raw text."""
    two_lines = (
        '{"tool": "search", "args": {"query": "process for purchasing replacement cable for '
        'VR headset", "k": 3}}\n'
        '{"tool": "search", "args": {"query": "process for purchasing additional GitHub '
        'Enterprise seats", "k": 3}}'
    )

    completion = parse_prompted_response(two_lines, known_tools=_KNOWN_TOOLS)

    assert completion.content is None
    first, second = completion.tool_calls
    assert first.name == "search"
    assert first.arguments["query"] == "process for purchasing replacement cable for VR headset"
    assert second.name == "search"
    assert second.arguments["query"] == "process for purchasing additional GitHub Enterprise seats"


def test_parse_prompted_response_three_tool_calls_all_batched() -> None:
    three = "\n".join(json.dumps({"tool": "search", "args": {"query": f"q{i}"}}) for i in range(3))

    completion = parse_prompted_response(three, known_tools=_KNOWN_TOOLS)

    assert len(completion.tool_calls) == 3
    assert [c.arguments["query"] for c in completion.tool_calls] == ["q0", "q1", "q2"]


def test_parse_prompted_response_tool_call_survives_an_unrelated_junk_value_alongside_it() -> None:
    """Postmortem follow-up redesign (D9): the OLD ">=2 objects" threshold made this an
    incoherent all-or-nothing batch check — a real tool call next to something else that ISN'T
    a tool call used to fall all the way back to raw/unstructured content, discarding the
    model's genuine intent to call ``search``. The new rule decides per-object: any object that
    DOES name a registered tool becomes a real call, full stop, regardless of what non-control
    JSON (here, a bare array) sits alongside it — provenance, not "does the whole reply look
    like a clean batch"."""
    mixed = json.dumps({"tool": "search", "args": {"query": "x"}}) + "\n" + json.dumps([1, 2, 3])

    completion = parse_prompted_response(mixed, known_tools=_KNOWN_TOOLS)

    (call,) = completion.tool_calls
    assert call.name == "search"
    assert call.arguments == {"query": "x"}
    assert completion.content is None


def test_parse_prompted_response_single_final_object_with_trailing_prose_is_extracted() -> None:
    """Postmortem follow-up redesign (D9): the OLD ">=2 objects" threshold treated "one tool
    object + trailing prose" and "prose + one tool object" as OPPOSITE outcomes depending on
    which side the prose fell on — the same incoherence applied to a lone ``{"final": ...}``,
    which used to be returned as raw, UNPARSED text (prose position deciding the outcome again).
    A single unambiguous ``{"final": ...}`` object is now always extracted, trailing chit-chat
    or not — symmetric with how a single tool object is now always honored (see the sibling
    test above)."""
    noisy = json.dumps({"final": "the answer"}) + " thanks!"

    completion = parse_prompted_response(noisy, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()
    assert completion.content == "the answer"
    assert completion.malformed is False


def test_scan_protocol_objects_finds_a_single_control_value() -> None:
    assert scan_protocol_objects(json.dumps({"final": "x"})) == [{"final": "x"}]


def test_scan_protocol_objects_returns_empty_on_malformed_input() -> None:
    assert scan_protocol_objects("not json at all") == []


def test_scan_protocol_objects_ignores_non_control_objects() -> None:
    """A legitimate ``format="json"`` answer must never be mistaken for the control channel."""
    assert scan_protocol_objects(json.dumps({"answer": "42", "confidence": "high"})) == []


def test_scan_protocol_objects_finds_calls_around_prose() -> None:
    """D73 regression: the first fix required the WHOLE reply to be back-to-back JSON, so one
    word of the model's own prose between or after the objects put the raw protocol back on the
    user's screen. Both shapes below were reproduced against the real parser."""
    a = {"tool": "search", "args": {"query": "VR cable", "k": 3}}
    b = {"tool": "search", "args": {"query": "GitHub seats", "k": 3}}
    between = f"{json.dumps(a)}\nand also\n{json.dumps(b)}"
    trailing = f"{json.dumps(a)}\n{json.dumps(b)}\nI will combine these."
    assert scan_protocol_objects(between) == [a, b]
    assert scan_protocol_objects(trailing) == [a, b]


def test_scan_protocol_objects_skips_a_truncated_leading_fragment() -> None:
    """A malformed fragment must not hide well-formed calls that follow it."""
    good = {"tool": "search", "args": {"query": "x", "k": 3}}
    assert scan_protocol_objects('{"tool": "search", "args": {"k": ' + f"\n{json.dumps(good)}") == [
        good
    ]


# --- D4/D5: scan_protocol_objects is bounded and RecursionError-safe (postmortem follow-up) --


def test_scan_protocol_objects_bounded_against_quadratic_adversarial_input() -> None:
    """D5: a run-on malformed input with no closing braces anywhere used to retry a failing
    ``raw_decode`` at every one of thousands of ``{`` positions, each attempt re-parsing most of
    what was left — quadratic, measured at ~1.5s for a 40KB input. Must now stay well under a
    generous ceiling (50ms — the real fix measures ~30ms) instead of blocking the event loop."""
    pathological = '{"a":' * 8000  # 40 KB, no closing brace anywhere

    start = time.perf_counter()
    result = scan_protocol_objects(pathological)
    elapsed_s = time.perf_counter() - start

    assert elapsed_s < 0.05, f"scan_protocol_objects took {elapsed_s * 1000:.1f}ms, expected <50ms"
    assert result == []  # nothing legitimately parses out of this input


def test_scan_protocol_objects_survives_pathological_nesting_without_recursion_error() -> None:
    """D4: sufficiently deep adversarial nesting (each ``:`` value itself opening a new
    object/array with no comma to close it) makes ``raw_decode`` recurse past Python's stack
    limit and raise ``RecursionError`` rather than a clean ``json.JSONDecodeError`` — this used
    to escape uncaught, all the way out of the SSE stream with no terminal "done" frame."""
    pathological = '{"a":[' * 5000

    result = scan_protocol_objects(pathological)  # must not raise RecursionError

    assert result == []


def test_parse_prompted_response_survives_pathological_nesting_without_recursion_error() -> None:
    """The same pathological input, through the full parser (not just the raw scanner) —
    ``AnswerPipeline.run`` depends on this never raising so the SSE stream always reaches
    "done"."""
    pathological = '{"a":[' * 5000

    completion = parse_prompted_response(pathological, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()


# --- D2/D3: key-order and quote-style agnostic malformed-control-message detection -----------


def test_parse_prompted_response_truncated_args_first_object_is_malformed() -> None:
    """D2: the original ``TRUNCATED_PROTOCOL_RE`` anchored on the opening brace being IMMEDIATELY
    followed by the ``tool``/``final`` key — a truncated object whose ``args`` key happens to
    come FIRST (a real shape: the model started with the argument it was most sure of) was
    neither scanned (it never parses) nor regex-matched, and used to leak straight through to
    the ``_strip_trailing_tool_json`` prose fallback as if it were a real (if odd) answer."""
    truncated = '{"args": {"query": "x"}, "tool": "sea'

    completion = parse_prompted_response(truncated, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()
    assert completion.malformed is True
    assert completion.content == truncated  # raw, for diagnostics — never shown to a user


def test_parse_prompted_response_single_quoted_python_dict_style_is_malformed() -> None:
    """D3: a model reverting to Python's ``repr()``-style single quotes instead of JSON's
    required double quotes never parses via ``json.raw_decode`` and must be recognized as a
    broken control message too, not silently treated as a genuine prose answer."""
    single_quoted = "{'tool': 'search', 'args': {'query': 'x'}}"

    completion = parse_prompted_response(single_quoted, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()
    assert completion.malformed is True


# --- D8: an unregistered "tool" name is a legitimate answer, never a leak or a malformed flag -


def test_parse_prompted_response_unregistered_tool_name_is_a_normal_answer_not_flagged() -> None:
    """D8: a ``format="json"`` answer whose OWN user-supplied schema happens to use "tool" as a
    field name (e.g. routing a support ticket to a system named "Jira") is well-formed JSON that
    legitimately has a "tool" key — but "Jira" is not a REGISTERED tool, so it must never be
    treated as a call, and — because it parses perfectly cleanly — must never be flagged
    ``malformed`` either. It is simply the model's real answer."""
    jira_answer = json.dumps({"tool": "Jira", "owner": "IT"})

    completion = parse_prompted_response(jira_answer, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()
    assert completion.malformed is False
    assert completion.content == jira_answer


# --- D9: provenance, not batch-shape, decides — one object + prose on EITHER side is a call --


def test_parse_prompted_response_single_tool_call_with_prose_on_both_sides_is_still_a_call() -> (
    None
):
    """D9: the model wanted to search — that does not stop being true just because it also said
    something conversational before AND after the call. Provenance (the object names a
    registered tool) decides this, not "is the whole reply cleanly nothing but N objects"."""
    noisy = (
        "Sure, let me check that for you.\n"
        + json.dumps({"tool": "search", "args": {"query": "onboarding checklist"}})
        + "\nOne moment please."
    )

    completion = parse_prompted_response(noisy, known_tools=_KNOWN_TOOLS)

    (call,) = completion.tool_calls
    assert call.name == "search"
    assert call.arguments == {"query": "onboarding checklist"}
    assert completion.content is None
    assert completion.malformed is False


# --- D10: an INTERIOR code fence must never be stripped (only a whole-reply wrapping pair) ---


def test_parse_prompted_response_interior_fence_is_not_glued_into_a_fabricated_tool_call() -> None:
    """D10: the prior fence-stripper (``re.MULTILINE``) deleted ANY line merely starting or
    ending with a fence marker, anywhere in the reply — not just a pair wrapping the whole
    thing. Reproduced against the OLD parser: a reply that legitimately explained something
    using an embedded fenced JSON example had BOTH its interior fence markers stripped, silently
    GLUING the prose-adjacent fragments on either side into a complete, parseable, and entirely
    FABRICATED ``search`` call the model never actually asked for — it only wanted to show an
    example inline. Verified against the real (buggy) old regex before this fix landed."""
    explained_with_example = 'Example call:\n```\n{"tool": "search",\n```\n"args": {"k": 3}}'

    # Sanity: the OLD code (fence-strip, THEN — since the result doesn't start with "{" —
    # trim to the first "{"/last "}") really did fabricate a call out of this exact input,
    # pinning the regression this test guards against as real, not hypothetical.
    _old_fence_re = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
    old_stripped = _old_fence_re.sub("", explained_with_example.strip()).strip()
    old_start, old_end = old_stripped.find("{"), old_stripped.rfind("}")
    old_candidate = old_stripped[old_start : old_end + 1]
    assert json.loads(old_candidate) == {"tool": "search", "args": {"k": 3}}  # the OLD bug

    completion = parse_prompted_response(explained_with_example, known_tools=_KNOWN_TOOLS)

    assert completion.tool_calls == ()  # no fabricated "search" call


async def test_prompted_mode_executes_both_batched_tool_calls_over_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through the real HTTP path (not just the pure parser): a prompted-mode
    response body carrying two tool-call lines comes back as a two-element ``tool_calls``
    tuple from :meth:`complete_with_tools`."""
    two_lines = (
        json.dumps({"tool": "search", "args": {"query": "a"}})
        + "\n"
        + json.dumps({"tool": "search", "args": {"query": "b"}})
    )

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": two_lines}}]})

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="prompted")

    result = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)

    assert len(result.tool_calls) == 2
    assert {c.arguments["query"] for c in result.tool_calls} == {"a", "b"}


# --- D73: auto mode's 429-vs-capability classification (2026-08-18 live-demo postmortem) -----


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Stub out the retry backoff so these tests run instantly; records the sleep durations
    actually requested for tests that want to assert on them."""
    slept: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("sift.adapters.llm.openai_compat.asyncio.sleep", _fake_sleep)
    return slept


async def test_auto_mode_429_retries_native_and_never_sticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient 429 on the native attempt must be retried (not immediately treated as 'no
    tool-calling support') and, once it succeeds, must NOT set the sticky fallback flag — the
    next call tries native again from scratch. This is the exact incident: a free-tier rate
    limit wrongly degraded the whole rest of the demo to prompted mode."""
    slept = _no_sleep(monkeypatch)
    calls: list[str] = []
    native_attempts = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal native_attempts
        body = json.loads(request.content)
        if "tools" not in body:
            calls.append("prompted")
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps({"final": "ok"})}}]}
            )
        native_attempts += 1
        calls.append("native")
        if native_attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "native ok"}}]}
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="auto")

    first = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert first.content == "native ok"
    assert calls == ["native", "native"]  # retried, never fell back to prompted
    assert slept  # the retry actually paused with backoff

    second = await completer.complete_with_tools([{"role": "user", "content": "again"}], _TOOLS)
    assert second.content == "native ok"
    # Not sticky: the second call's FIRST attempt is native again, no prompted fallback at all.
    assert calls == ["native", "native", "native"]


async def test_auto_mode_429_exhausting_all_retries_falls_back_for_that_call_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When native keeps 429ing past every retry, THAT call degrades to prompted (never a bare
    exception), but the failure is NOT sticky — the very next call tries native again."""
    _no_sleep(monkeypatch)
    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" in body:
            calls.append("native")
            return httpx.Response(429, json={"error": "rate limited"})
        calls.append("prompted")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps({"final": "fallback"})}}]}
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter(
        "http://llm/v1", "gpt", tool_mode="auto", native_retry_attempts=2
    )

    first = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert first.content == "fallback"
    # 2 native attempts (the configured native_retry_attempts budget), then prompted for THIS
    # call only.
    assert calls == ["native", "native", "prompted"]

    calls.clear()
    second = await completer.complete_with_tools([{"role": "user", "content": "again"}], _TOOLS)
    assert second.content == "fallback"
    # Still not sticky: the second call independently retries native from scratch too.
    assert calls == ["native", "native", "prompted"]


async def test_auto_mode_genuine_capability_error_sticks_immediately_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-retryable error (here, a 404 — the backend rejecting an unrecognized ``tools``
    param, not a rate limit) is a genuine capability signal: no retry attempts are burned on
    it, and it DOES set the sticky fallback flag for the rest of the process."""
    slept = _no_sleep(monkeypatch)
    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" in body:
            calls.append("native")
            return httpx.Response(404, json={"error": "unknown parameter: tools"})
        calls.append("prompted")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps({"final": "ok"})}}]}
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter(
        "http://llm/v1", "gpt", tool_mode="auto", native_retry_attempts=3
    )

    first = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert first.content == "ok"
    assert calls == ["native", "prompted"]  # exactly ONE native attempt, no retry burned
    assert slept == []  # no backoff for a non-retryable error

    second = await completer.complete_with_tools([{"role": "user", "content": "again"}], _TOOLS)
    assert second.content == "ok"
    # Sticky: the second call never retries native at all.
    assert calls == ["native", "prompted", "prompted"]


# --- D6: a 2xx with a garbled body is retryable, never a capability signal (postmortem audit) -


async def test_auto_mode_garbled_2xx_error_envelope_retries_and_never_sticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D6: a 2xx response whose body is missing the expected OpenAI shape (an error envelope
    with no ``choices`` at all — a proxy/backend hiccup returning its own error body with the
    wrong status code) must be retried like a 429/5xx, and must NEVER set the sticky fallback
    flag once it eventually succeeds — this has nothing to do with tool-calling support."""
    slept = _no_sleep(monkeypatch)
    calls: list[str] = []
    native_attempts = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal native_attempts
        body = json.loads(request.content)
        if "tools" not in body:
            calls.append("prompted")
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps({"final": "ok"})}}]}
            )
        native_attempts += 1
        calls.append("native")
        if native_attempts == 1:
            return httpx.Response(200, json={"error": "upstream hiccup"})  # no "choices" at all
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "native ok"}}]}
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="auto")

    first = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert first.content == "native ok"
    assert calls == ["native", "native"]  # retried, never fell back to prompted
    assert slept  # the retry actually paused with backoff

    second = await completer.complete_with_tools([{"role": "user", "content": "again"}], _TOOLS)
    assert second.content == "native ok"
    # Not sticky: the second call's FIRST attempt is native again, no prompted fallback at all.
    assert calls == ["native", "native", "native"]


async def test_auto_mode_non_json_2xx_body_retries_and_never_sticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D6: an HTML proxy/gateway error page slipping through with a 200 status (not even valid
    JSON, so ``response.json()`` itself raises) is classified the SAME way as a garbled-but-
    valid-JSON error envelope above — retried, never sticky."""
    slept = _no_sleep(monkeypatch)
    calls: list[str] = []
    native_attempts = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal native_attempts
        body = json.loads(request.content)
        if "tools" not in body:
            calls.append("prompted")
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps({"final": "ok"})}}]}
            )
        native_attempts += 1
        calls.append("native")
        if native_attempts == 1:
            return httpx.Response(200, content=b"<html><body>502 Bad Gateway</body></html>")
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "native ok"}}]}
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="auto")

    first = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert first.content == "native ok"
    assert calls == ["native", "native"]
    assert slept


# --- postmortem follow-up audit: sticky fallback is a bounded TTL, not the process lifetime --


async def test_native_unsupported_ttl_expiry_retries_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A GENUINE capability error still sticks (native skipped) while the TTL hasn't lapsed, but
    once ``time.monotonic()`` passes the deadline, "auto" mode tries native again from scratch —
    a wrong capability verdict self-heals instead of degrading the rest of the process forever."""
    _no_sleep(monkeypatch)
    calls: list[str] = []
    fake_now = 1000.0
    monkeypatch.setattr("sift.adapters.llm.openai_compat.time.monotonic", lambda: fake_now)

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" in body:
            calls.append("native")
            return httpx.Response(404, json={"error": "unknown parameter: tools"})
        calls.append("prompted")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps({"final": "ok"})}}]}
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter(
        "http://llm/v1", "gpt", tool_mode="auto", native_unsupported_ttl_s=60.0
    )

    first = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert first.content == "ok"
    assert calls == ["native", "prompted"]  # genuine capability error -> sticky set

    calls.clear()
    fake_now += 30.0  # 30s elapsed — still within the 60s TTL
    second = await completer.complete_with_tools([{"role": "user", "content": "again"}], _TOOLS)
    assert second.content == "ok"
    assert calls == ["prompted"]  # still sticky: native skipped entirely, no attempt at all

    calls.clear()
    fake_now += 31.0  # 61s elapsed total — past the 60s TTL
    third = await completer.complete_with_tools([{"role": "user", "content": "once more"}], _TOOLS)
    assert third.content == "ok"
    assert calls == ["native", "prompted"]  # TTL lapsed: native retried from scratch


# --- D12: httpx.LocalProtocolError is a bug in OUR request, never retried; TimeoutException ---
# --- is a redundant (already-covered) TransportError subclass --------------------------------


def test_is_retryable_error_excludes_local_protocol_error() -> None:
    assert _is_retryable_error(httpx.LocalProtocolError("bad header")) is False


def test_is_retryable_error_still_covers_timeout_via_transport_error() -> None:
    assert _is_retryable_error(httpx.ConnectTimeout("timed out")) is True


# --- D13: the docstring must not reference a function that no longer exists ------------------


def test_parse_prompted_response_docstring_has_no_stale_function_reference() -> None:
    """D13: ``parse_prompted_response``'s docstring used to cite
    ``_extract_back_to_back_json_values``, a function that no longer exists in this module —
    stale documentation pointing a future reader at dead code."""
    doc = parse_prompted_response.__doc__ or ""
    assert "_extract_back_to_back_json_values" not in doc


# --- postmortem follow-up audit, second pass (Opus audit of the provenance redesign) --------
# Every case below was a HIGH finding reproduced end to end against the first redesign; each is
# pinned here so the next audit starts from this floor rather than rediscovering it.

_KNOWN = ("search", "list_documents")


def test_two_finals_are_malformed_never_leaked() -> None:
    """The first redesign gated the malformed catch on 'no control objects found at all', so a
    reply with TWO finals fell through to the prose path and streamed the first one verbatim."""
    out = parse_prompted_response(
        '{"final": "answer one"}\n{"final": "answer two"}', known_tools=_KNOWN
    )
    assert out.malformed is True
    assert not out.tool_calls


def test_unregistered_tool_is_malformed_never_leaked() -> None:
    """A hallucinated or misspelled tool name is the likeliest real-world malformed shape; the
    first redesign returned the whole object verbatim as the answer."""
    for name in ("web_search", 42, "serach"):
        out = parse_prompted_response(
            json.dumps({"tool": name, "args": {"query": "travel policy"}}), known_tools=_KNOWN
        )
        assert out.malformed is True, name
        assert not out.tool_calls, name


def test_known_tool_matches_case_and_whitespace_insensitively() -> None:
    for spelled in ("Search", " search ", "SEARCH"):
        out = parse_prompted_response(
            json.dumps({"tool": spelled, "args": {"query": "x"}}), known_tools=_KNOWN
        )
        assert [c.name for c in out.tool_calls] == ["search"], spelled


def test_prompted_prose_that_quotes_a_final_keeps_the_prose() -> None:
    """D7 in prompted mode: a genuine answer that merely QUOTES a {"final"} object used to be
    replaced by that object's value. The prose is the answer; the quoted protocol text is
    removed so nothing protocol-shaped reaches the user."""
    text = (
        'To finish, the model emits {"final": "your answer"} and stops. That is the whole '
        "protocol, and it matters because otherwise the loop never ends."
    )
    out = parse_prompted_response(text, known_tools=_KNOWN)
    assert out.malformed is False and not out.tool_calls
    assert out.content is not None
    # Fourth-pass audit: a short final inside long prose is ambiguous (a quote, or a short real
    # answer after reasoning), so BOTH are delivered: the prose with the object excised, then
    # the value. No protocol text, nothing lost in either reading.
    assert '{"final"' not in out.content
    assert out.content.startswith("To finish, the model emits")
    assert out.content.endswith("the loop never ends.\n\nyour answer")


def test_final_with_short_chatter_is_still_the_answer() -> None:
    out = parse_prompted_response('Sure, here it is: {"final": "42"}', known_tools=_KNOWN)
    assert out.content == "42"


def test_json_answer_with_tool_key_and_other_keys_is_an_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D8 at the parser: {"tool": "Jira", "owner": "IT"} is not control-shaped."""
    out = parse_prompted_response('{"tool": "Jira", "owner": "IT"}', known_tools=_KNOWN)
    assert not out.tool_calls and out.malformed is False
    assert out.content == '{"tool": "Jira", "owner": "IT"}'


def test_well_formed_json_that_nests_a_tool_key_is_not_malformed() -> None:
    """The truncated-signature regex only fires when the whole reply fails to parse."""
    out = parse_prompted_response(
        '{"wrapper": {"tool": "search", "args": {"query": "x"}}}', known_tools=_KNOWN
    )
    assert out.malformed is False and not out.tool_calls


def test_scan_is_not_starved_by_template_braces_in_prose() -> None:
    """The first cap counted successes and every cheap failure alike, so ~64 {placeholder}
    braces hid a real control object after them. The budget is now re-parse WORK, so a
    thousand cheap failures cost almost nothing."""
    text = "".join(f"use {{p{i}}} here\n" for i in range(1000)) + '{"final": "REAL"}'
    assert scan_protocol_objects(text) == [{"final": "REAL"}]


@pytest.mark.asyncio
async def test_auto_mode_401_falls_back_for_this_call_only_and_never_sticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """401/403 are neither transient nor a verdict on tool-calling support: prompted for THIS
    call, native tried again next call. The first redesign stuck on them for the whole TTL."""
    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" in body:
            calls.append("native")
            return httpx.Response(401, json={"error": "invalid api key"})
        calls.append("prompted")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps({"final": "ok"})}}]}
        )

    _patch_transport(monkeypatch, _handler)
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="auto")
    await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    await completer.complete_with_tools([{"role": "user", "content": "again"}], _TOOLS)
    assert calls == ["native", "prompted", "native", "prompted"]


@pytest.mark.asyncio
async def test_auto_mode_408_is_retried_like_a_429(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "tools" in body:
            calls.append("native")
            if len(calls) == 1:
                return httpx.Response(408, json={"error": "request timeout"})
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "hello", "tool_calls": []}}]}
            )
        calls.append("prompted")
        return httpx.Response(200, json={"choices": [{"message": {"content": "x"}}]})

    _patch_transport(monkeypatch, _handler)
    monkeypatch.setattr("sift.adapters.llm.openai_compat._RETRY_BACKOFF_S", (0.0, 0.0, 0.0))
    completer = OpenAICompatCompleter("http://llm/v1", "gpt", tool_mode="auto")
    out = await completer.complete_with_tools([{"role": "user", "content": "hi"}], _TOOLS)
    assert out.content == "hello"
    assert calls == ["native", "native"]


# --- third-pass audit -------------------------------------------------------------------------


def test_registered_tool_with_an_extra_chatty_key_is_still_a_call() -> None:
    """The exact-key-set gate let ``{"tool": "search", ..., "reason": ...}`` fall through as a
    JSON answer and stream verbatim: the original incident shape. The registry decides first."""
    out = parse_prompted_response(
        '{"tool": "search", "args": {"query": "x"}, "reason": "look it up"}', known_tools=_KNOWN
    )
    assert [c.name for c in out.tool_calls] == ["search"]


def test_final_with_an_extra_chatty_key_is_still_the_answer() -> None:
    out = parse_prompted_response('{"final": "the answer", "note": "done"}', known_tools=_KNOWN)
    assert out.content == "the answer" and out.malformed is False


def test_reply_that_is_only_a_fence_or_blank_is_malformed() -> None:
    for text in ("```json\n```", "```\n```", "   "):
        out = parse_prompted_response(text, known_tools=_KNOWN)
        assert out.malformed is True, repr(text)


def test_reasoning_prose_then_a_real_final_delivers_the_final() -> None:
    """A long final after long prose is the answer the model was told to produce, not a quote."""
    final = "The purchase needs a Carrito de Compra in SAP approved by the Area Manager first."
    text = ("Let me think about this carefully. " * 4) + json.dumps({"final": final})
    out = parse_prompted_response(text, known_tools=_KNOWN)
    assert out.content == final


def test_known_tool_alongside_unknown_tool_runs_the_known_one() -> None:
    text = '{"tool":"search","args":{"query":"a"}}\n{"tool":"web_search","args":{}}'
    out = parse_prompted_response(text, known_tools=_KNOWN)
    assert [c.name for c in out.tool_calls] == ["search"]
