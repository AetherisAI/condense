"""OpenAI-compatible chat adapter — (system, user) → recap text over async HTTP.

Implements the :class:`~sift.core.ports.Completer` port by POSTing the two turns to an
OpenAI-style ``{base_url}/chat/completions`` endpoint (``base_url`` already ends in ``/v1``)
and returning ``choices[0].message.content``. One ``httpx.AsyncClient`` per call (no shared
state), mirroring the embeddings adapter.

Also implements :class:`~sift.core.ports.ToolCompleter` (WP v0.2.0 T3, D40) —
:meth:`complete_with_tools` drives the ``/v1/answer`` tool loop against ANY OpenAI-compatible
model, not just one that supports native function-calling:

- **native** — sends the registry's ``tools=[...]`` verbatim as the request's ``tools``
  param (``tool_choice="auto"``); a ``tool_calls`` reply maps onto
  :class:`~sift.core.types.ToolCall`, otherwise the message content is the final answer.
- **prompted** — a strict-JSON ReAct fallback for a model with no native tool-calling: the
  tool definitions are rendered into a system instruction (one JSON object per turn, either
  ``{"tool": ..., "args": ...}`` or ``{"final": ...}``), and the transcript's tool exchanges
  are flattened into plain user/assistant turns first (a "tool"-role message or an
  assistant's ``tool_calls`` field would confuse a backend that never advertised tool
  support).
- **auto** (``Settings.answer_tool_mode``, the default) — tries native once; ANY error (HTTP,
  malformed shape, ...) falls back to prompted for that call AND sticks for the rest of this
  instance's process lifetime (never retries native again) — cheap, and avoids repeatedly
  paying a doomed native attempt's latency/error on every subsequent turn.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import httpx

from sift.core.types import ToolCall, ToolCompletion

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class OpenAICompatCompleter:
    """Completer + ToolCompleter backed by an OpenAI-compatible ``/chat/completions`` endpoint."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        tool_mode: Literal["auto", "native", "prompted"] = "auto",
        answer_max_tokens: int | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._tool_mode = tool_mode
        # Separate from `max_tokens` (the recap's cap, via `.complete()`): `Settings
        # .answer_max_tokens` bounds ONLY the `/v1/answer` loop's completions
        # (`.complete_with_tools()`), which may need a longer budget for tool-call reasoning.
        self._answer_max_tokens = answer_max_tokens
        # Sticky for the process lifetime once "auto" has seen native fail once (module docstring).
        self._native_unsupported = False
        # One keep-alive client reused across every `_post` for this (long-lived, per-container)
        # completer, so the repeated same-host completions in one `/v1/answer` tool-loop reuse a
        # connection instead of paying a fresh TCP+TLS handshake per round-trip. Created lazily on
        # first use (construction has no `await`, so the check-and-set is atomic on the loop).
        self._client: httpx.AsyncClient | None = None

    async def complete(self, system: str, user: str) -> str:
        headers = self._headers()
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self._max_tokens is not None:
            payload["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        data = await self._post(payload, headers)
        return data["choices"][0]["message"]["content"]

    # --- ToolCompleter -------------------------------------------------------------------

    async def complete_with_tools(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> ToolCompletion:
        mode = self._tool_mode
        if mode == "native":
            return await self._complete_native(messages, tools)
        if mode == "prompted":
            return await self._complete_prompted(messages, tools)
        # "auto": try native once; any failure falls back to prompted and stays there.
        if not self._native_unsupported:
            try:
                return await self._complete_native(messages, tools)
            except Exception:
                logger.warning(
                    "native tool-calling failed against %s; falling back to the prompted "
                    "strict-JSON mode for the rest of this process",
                    self._base_url,
                    exc_info=True,
                )
                self._native_unsupported = True
        return await self._complete_prompted(messages, tools)

    async def _complete_native(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> ToolCompletion:
        headers = self._headers()
        payload: dict[str, object] = {
            "model": self._model,
            "messages": list(messages),
            "tools": list(tools),
            "tool_choice": "auto",
        }
        if self._answer_max_tokens is not None:
            payload["max_tokens"] = self._answer_max_tokens
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        data = await self._post(payload, headers)
        message = data["choices"][0]["message"]
        raw_calls = message.get("tool_calls") or []
        if raw_calls:
            return ToolCompletion(tool_calls=tuple(_parse_native_tool_call(c) for c in raw_calls))
        content = _coerce_message_content(message.get("content"))
        return ToolCompletion(content=_strip_trailing_tool_json(content))

    async def _complete_prompted(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> ToolCompletion:
        headers = self._headers()
        flattened = _flatten_for_prompted(messages)
        flattened.append({"role": "system", "content": _render_prompted_instructions(tools)})
        payload: dict[str, object] = {"model": self._model, "messages": flattened}
        if self._answer_max_tokens is not None:
            payload["max_tokens"] = self._answer_max_tokens
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        data = await self._post(payload, headers)
        content = _coerce_message_content(data["choices"][0]["message"].get("content"))
        return parse_prompted_response(content)

    # --- plumbing -------------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}

    def _get_client(self) -> httpx.AsyncClient:
        """The reused keep-alive client, created on first use (no ``await`` → race-free on loop)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def _post(self, payload: Mapping[str, object], headers: Mapping[str, str]) -> Any:
        response = await self._get_client().post(
            f"{self._base_url}/chat/completions", json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        """Close the reused client — call from a lifespan shutdown when teardown is wired."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# --- content normalization (D40 amendment: BUG #2) --------------------------------------------


def _coerce_message_content(raw: Any) -> str:
    """Coerce an OpenAI-shape ``message.content`` into a plain ``str`` — ``ToolCompletion.content``
    must ALWAYS be ``str`` (it flows straight into the conversation store, which binds it into a
    SQL ``TEXT`` column).

    Most providers return a plain string. Mistral (and reportedly others) return a LIST of
    content-block dicts for a multi-cited answer instead — ``{"type": "text", "text": ...}``
    interleaved with ``{"type": "reference", "reference_ids": [...]}`` — never a string. Passing
    that raw list downstream crashed the conversation store's DB bind with an opaque
    ``ValueError: Unsupported parameter type`` far from the real cause (D40 amendment). Every
    ``text`` block's text is concatenated in order; a ``reference`` block carries no
    human-readable text of its own (just internal citation-target ids) so it is dropped rather
    than leaking a raw id into the answer.
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for block in raw:
            if isinstance(block, Mapping) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(raw)  # pragma: no cover - defensive: no known provider returns another shape


def _strip_trailing_tool_json(text: str) -> str:
    """Strip one stray tool-call-args-shaped JSON object glued onto the end of otherwise-prose
    ``text`` (D42 amendment, D43 fix).

    Observed on some real-Mistral turns, both native and prompted: the visible final answer
    ends with a raw fragment like ``...(p.1){"query": "...", "k": 20}`` — args that look exactly
    like a tool call's arguments but were never routed through the structured ``tool_calls``/
    ``{"tool": ...}`` control channel, just emitted as plain trailing text. ``ToolCompletion
    .content`` must NEVER carry that JSON tail through to the user.

    Bracket-matched backward from the end (handles a JSON object with its own nested braces,
    e.g. a ``filters`` sub-object) rather than a naive last-``{``/first-``}`` scan, which would
    mis-locate the opening brace of a nested object. A no-op unless ``text`` both ends with
    ``}`` AND there is non-empty prose before the matching ``{`` — a reply that IS one whole
    JSON object (json-mode's final answer, or a control object already handled by
    :func:`parse_prompted_response`'s ``tool``/``final`` branches) is left completely untouched,
    since stripping it would erase the entire answer.
    """
    stripped = text.rstrip()
    if not stripped.endswith("}"):
        return text
    depth = 0
    start = None
    for i in range(len(stripped) - 1, -1, -1):
        ch = stripped[i]
        if ch == "}":
            depth += 1
        elif ch == "{":
            depth -= 1
            if depth == 0:
                start = i
                break
    if start is None:
        return text
    prefix = stripped[:start].rstrip()
    if not prefix:
        return text
    try:
        parsed = json.loads(stripped[start:])
    except (TypeError, ValueError):
        return text
    if not isinstance(parsed, dict):
        return text
    return prefix


# --- native tool-call parsing --------------------------------------------------------------


def _parse_native_tool_call(raw: Mapping[str, Any]) -> ToolCall:
    """Map one OpenAI-shape ``tool_calls[]`` entry onto a :class:`~sift.core.types.ToolCall`.

    ``function.arguments`` is a JSON *string* per the OpenAI spec — malformed JSON degrades to
    an empty-args call rather than crashing the whole loop over one bad call.
    """
    call_id = str(raw.get("id") or f"call_{uuid.uuid4().hex[:8]}")
    function = raw.get("function") or {}
    name = str(function.get("name", ""))
    raw_args = function.get("arguments")
    try:
        arguments = json.loads(raw_args) if raw_args else {}
    except (TypeError, ValueError):
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    return ToolCall(id=call_id, name=name, arguments=arguments)


# --- prompted strict-JSON fallback ----------------------------------------------------------


def _flatten_for_prompted(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Reduce the native-shaped transcript to plain ``{role, content}`` turns.

    A model with no native tool-calling support was never told about a ``"tool"`` role or an
    assistant's ``tool_calls`` field — sending either verbatim risks a strict backend rejecting
    the request outright. Both get rewritten into a plain, readable user/assistant turn
    describing what happened, so any OpenAI-compatible ``/chat/completions`` endpoint accepts
    the request regardless of whether it understands tool-calling at all.
    """
    flattened: list[dict[str, str]] = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "tool":
            name = msg.get("name", "tool")
            flattened.append(
                {"role": "user", "content": f"[tool result: {name}] {msg.get('content', '')}"}
            )
        elif role == "assistant" and msg.get("content") is None and msg.get("tool_calls"):
            calls_desc = "; ".join(
                f"{tc['function']['name']}({tc['function']['arguments']})"
                for tc in msg["tool_calls"]
            )
            flattened.append({"role": "assistant", "content": f"[called tool(s): {calls_desc}]"})
        else:
            flattened.append({"role": role, "content": str(msg.get("content") or "")})
    return flattened


def _render_prompted_instructions(tools: Sequence[Mapping[str, Any]]) -> str:
    """Render the registry's tool definitions into a strict-JSON-turn instruction."""
    lines = [
        "You have NO native tool-calling support, but the following tools exist. Respond with "
        "EXACTLY one JSON object and nothing else (no prose, no markdown fences):",
        '- To call a tool: {"tool": "<name>", "args": {...}}',
        '- To give your final answer: {"final": "<answer text>"}',
        "Available tools:",
    ]
    for entry in tools:
        function = entry.get("function", entry)
        name = function.get("name", "")
        description = function.get("description", "")
        params = function.get("parameters", {})
        lines.append(f"- {name}: {description} — parameters JSON Schema: {json.dumps(params)}")
    return "\n".join(lines)


def parse_prompted_response(text: str) -> ToolCompletion:
    """Parse one prompted-mode reply into a :class:`~sift.core.types.ToolCompletion`.

    Defensive by design — a prompted model is not a JSON API: it may wrap its JSON in a
    markdown code fence, or occasionally ignore the instruction and reply in plain prose (or
    reply in prose with a stray tool-args-shaped JSON fragment glued onto the end — D42
    amendment, D43). Any of that degrades to treating the reply as the final answer rather than
    crashing the loop (with a trailing tool-args JSON tail scrubbed off first, see
    :func:`_strip_trailing_tool_json`); only a well-formed ``{"tool": ...}``/``{"final": ...}``
    object is treated as structured.
    """
    stripped = _FENCE_RE.sub("", text.strip()).strip()
    candidate = stripped
    if not candidate.startswith("{"):
        # Tolerate leading/trailing chatter around the one JSON object we actually want.
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = candidate[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except (TypeError, ValueError):
        return ToolCompletion(content=_strip_trailing_tool_json(text))
    if not isinstance(parsed, dict):
        return ToolCompletion(content=_strip_trailing_tool_json(text))
    if "tool" in parsed:
        args = parsed.get("args")
        return ToolCompletion(
            tool_calls=(
                ToolCall(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    name=str(parsed["tool"]),
                    arguments=args if isinstance(args, dict) else {},
                ),
            )
        )
    if "final" in parsed:
        return ToolCompletion(content=str(parsed["final"]))
    return ToolCompletion(content=_strip_trailing_tool_json(text))
