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
- **auto** (``Settings.answer_tool_mode``, the default) — tries native, retrying a transient
  error (HTTP 429/5xx, a timeout/connection drop, or a 2xx with a garbled body — see below) with
  backoff before falling back to prompted for THAT call only; a genuine capability failure (a
  400/404/422 the backend uses to reject an unknown ``tools`` param) falls back to prompted AND
  sticks for ``Settings.answer_native_unsupported_ttl_s`` seconds (a bounded TTL, NOT the
  process lifetime — see below), never retrying native again until the TTL lapses — cheap, and
  avoids repeatedly paying a doomed native attempt's latency/error on every subsequent turn.
  D73 (2026-08-18 live-demo postmortem): a transient 429 was previously conflated with "this
  backend has no tool-calling support" and stuck forever, degrading an entire desktop-app
  session to the strictly less reliable prompted mode after one rate limit — see
  :func:`_is_retryable_error`. Postmortem FOLLOW-UP audit (same date): (1) a 2xx response whose
  body isn't the expected OpenAI shape (an error envelope with no ``choices``, an HTML proxy
  page slipping through with a 200 status, ...) was wrongly falling into the non-retryable
  branch and setting the sticky flag — it is exactly as transient/backend-side as a 429, see
  :class:`_MalformedNativeResponseError`; (2) "sticks for the rest of this instance's process
  lifetime" was itself a bug: a WRONG capability verdict (a backend that starts supporting
  ``tools`` mid-deployment, or was misclassified by a transient condition this module didn't
  yet know to treat as retryable) degraded an entire long-lived process forever with no way to
  recover short of a restart — the sticky state is now a monotonic deadline
  (``Settings.answer_native_unsupported_ttl_s``, default 30 minutes) rather than a permanent
  bool, so a wrong verdict self-heals.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import Collection, Mapping, Sequence
from typing import Any, Literal

import httpx

from sift.core.toolprotocol import TRUNCATED_PROTOCOL_RE, scan_protocol_objects
from sift.core.types import ToolCall, ToolCompletion

logger = logging.getLogger(__name__)

# Wraps a code fence around the ENTIRE reply only (D10 — see _strip_wrapping_fence): the prior
# `_FENCE_RE` (`re.MULTILINE`, stripped any line merely starting/ending with a fence marker,
# anywhere in the text) is gone — see _strip_wrapping_fence's docstring for the exact incident
# it caused.
_WRAPPING_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)

# Fixed backoff between native-mode retries — same fixed tuple and same rationale as the
# embeddings adapter's 429 retry (D34, ``adapters/embedding/openai_compat.py``): only the
# attempt *count* is a plausible per-deployment tuning knob, the delays themselves are not.
_RETRY_BACKOFF_S: tuple[float, ...] = (0.5, 2.0, 8.0)


class _MalformedNativeResponseError(Exception):
    """A native-mode POST came back 2xx but its body was not the expected OpenAI-compatible
    shape (D6, postmortem follow-up audit): an error envelope with no ``choices`` (``KeyError``/
    ``IndexError``/``TypeError`` reading ``data["choices"][0]["message"]``), or a body that
    isn't even valid JSON at all (``json.JSONDecodeError`` from ``response.json()`` — an HTML
    proxy/gateway error page slipping through with a 200 status is a real observed shape).

    Raised by :meth:`OpenAICompatCompleter._complete_native` and classified RETRYABLE by
    :func:`_is_retryable_error` — a garbled 2xx body is exactly as transient/backend-side as a
    429 or 5xx (a proxy hiccup, a backend momentarily returning its own error page with the
    wrong status code, ...), never a signal that the backend genuinely lacks tool-calling
    support. Before this existed, this exact shape fell through `_is_retryable_error`'s
    catch-all "anything else is a capability signal" branch and set the sticky fallback flag
    off a condition that had nothing to do with tool-calling support at all.
    """


def _is_retryable_error(exc: Exception) -> bool:
    """Whether ``exc`` (raised from one native-mode POST) is a transient condition worth
    retrying, rather than a signal that the backend genuinely lacks tool-calling support.

    HTTP 429 (rate limit) and 5xx (server-side trouble) are retryable, per the SAME principle
    already applied to the embeddings adapter (D34): a 429 is retryable, not a real failure. A
    2xx with a garbled body is retryable too (D6 — see :class:`_MalformedNativeResponseError`).
    A connection drop or a timeout is retryable for the same reason — EXCEPT
    ``httpx.LocalProtocolError`` (postmortem follow-up audit, D12): it signals a bug in the
    request WE built (a malformed header, an invalid URL composition, ...), not a transient
    backend condition, so retrying it would just fail identically every time; it is technically
    an ``httpx.TransportError`` subclass, so it must be excluded explicitly, ahead of the
    blanket ``TransportError`` check below. ``httpx.TimeoutException`` is likewise an
    ``httpx.TransportError`` subclass (D12: the old explicit check for it here was redundant —
    dropped, the blanket check already covers it).

    Anything else — a 400/404/422 the backend uses to reject an unrecognized ``tools`` param —
    is treated as a genuine capability signal and is NOT retried here; that is exactly the
    distinction D73's postmortem found missing (a 429 was wrongly treated as "no tool-calling
    support" and stuck for the rest of the process).
    """
    if isinstance(exc, _MalformedNativeResponseError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        # 408 (Request Timeout) and 409 (Conflict) are textbook transients, not verdicts on
        # what the backend supports; treat them like a 429.
        return status in (408, 409, httpx.codes.TOO_MANY_REQUESTS) or status >= 500
    if isinstance(exc, httpx.LocalProtocolError):
        return False
    return isinstance(exc, httpx.TransportError)


# The ONLY statuses that may make the native-tools fallback sticky: what an OpenAI-compatible
# backend answers when it does not understand the ``tools`` param at all. Everything else that
# is not retryable (401, 403, ...) fails THIS call and falls back to prompted for THIS call
# only: an expired key or a quota block says nothing about tool-calling support, and sticking
# on it would keep the whole process in prompted mode for the TTL for no reason (postmortem
# follow-up audit).
_CAPABILITY_FAILURE_STATUSES = frozenset({400, 404, 422})


def _is_capability_failure(exc: Exception) -> bool:
    return (
        isinstance(exc, httpx.HTTPStatusError)
        and exc.response.status_code in _CAPABILITY_FAILURE_STATUSES
    )


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
        native_retry_attempts: int = 3,
        native_unsupported_ttl_s: float = 1800.0,
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
        # Total attempts (first try + retries) "auto" mode gives a native call that keeps
        # failing with a RETRYABLE error (see `_is_retryable_error`) before giving up on native
        # for that one call — config-driven via `Settings.answer_native_retry_attempts` (D73).
        self._native_retry_attempts = native_retry_attempts
        # Postmortem follow-up audit: how long a GENUINE capability verdict (module docstring)
        # stays sticky, config-driven via `Settings.answer_native_unsupported_ttl_s`.
        self._native_unsupported_ttl_s = native_unsupported_ttl_s
        # A monotonic DEADLINE, not a bool (postmortem follow-up audit): `None` means native is
        # currently believed supported; a float means "auto" saw a GENUINE capability error
        # (module docstring) and native stays skipped until `time.monotonic()` passes this
        # value, after which the verdict is retried from scratch — a wrong verdict self-heals
        # instead of degrading the rest of the process's lifetime. A transient 429/5xx/timeout/
        # garbled-2xx-body is retried instead and never sets this (D73, D6; see
        # `_is_retryable_error`).
        self._native_unsupported_until: float | None = None
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
        # "auto": try native, retrying a transient error with backoff; only a genuine
        # capability error falls back to prompted AND sticks, bounded by a TTL (D73, postmortem
        # follow-up audit — see the module docstring and _is_retryable_error).
        native_unsupported = (
            self._native_unsupported_until is not None
            and time.monotonic() < self._native_unsupported_until
        )
        if not native_unsupported:
            for attempt in range(self._native_retry_attempts):
                try:
                    return await self._complete_native(messages, tools)
                except Exception as exc:
                    retryable = _is_retryable_error(exc)
                    if retryable and attempt < self._native_retry_attempts - 1:
                        logger.warning(
                            "native tool-calling hit a transient error against %s (attempt "
                            "%d/%d); retrying with backoff, NOT disabling native",
                            self._base_url,
                            attempt + 1,
                            self._native_retry_attempts,
                            exc_info=True,
                        )
                        backoff = _RETRY_BACKOFF_S[min(attempt, len(_RETRY_BACKOFF_S) - 1)]
                        await asyncio.sleep(backoff)
                        continue
                    if retryable:
                        logger.warning(
                            "native tool-calling against %s stayed rate-limited/unavailable "
                            "after %d attempt(s); falling back to prompted mode for THIS call "
                            "only (native will be tried again next call, not disabled)",
                            self._base_url,
                            self._native_retry_attempts,
                            exc_info=True,
                        )
                    elif _is_capability_failure(exc):
                        logger.warning(
                            "native tool-calling failed against %s; falling back to the "
                            "prompted strict-JSON mode for %.0fs (will retry native after that)",
                            self._base_url,
                            self._native_unsupported_ttl_s,
                            exc_info=True,
                        )
                        self._native_unsupported_until = (
                            time.monotonic() + self._native_unsupported_ttl_s
                        )
                    else:
                        # 401/403/whatever else: neither transient nor a capability verdict.
                        # Prompted for THIS call only; native is tried again next call.
                        logger.warning(
                            "native tool-calling failed against %s with a non-retryable, "
                            "non-capability error; falling back to prompted mode for THIS "
                            "call only",
                            self._base_url,
                            exc_info=True,
                        )
                    break
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
        # D6 (postmortem follow-up audit): a 2xx whose body isn't the expected OpenAI shape
        # (an error envelope with no `choices`, or a body that isn't even valid JSON — an HTML
        # proxy/gateway page slipping through with a 200 status) must never be treated as a
        # genuine capability signal — see `_MalformedNativeResponseError`'s docstring. Both the
        # HTTP call (`response.json()` can raise `json.JSONDecodeError`) and the shape access
        # below are covered by this one try/except; any `httpx.*` exception from `_post` itself
        # (a real transport/status error) is NOT in this tuple and propagates unchanged.
        try:
            data = await self._post(payload, headers)
            message = data["choices"][0]["message"]
            raw_calls = message.get("tool_calls") or []
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise _MalformedNativeResponseError(
                f"native tool-calling response from {self._base_url} was not the expected "
                "OpenAI-compatible shape"
            ) from exc
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
        # Same shape guard as the native path (postmortem follow-up audit: the two paths handled
        # the identical backend condition differently). A 2xx that is not the expected shape is
        # a transient upstream fault; surface it as one so the answer loop's own error handling
        # can end the turn with a diagnostic instead of a bare KeyError.
        try:
            data = await self._post(payload, headers)
            content = _coerce_message_content(data["choices"][0]["message"].get("content"))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise _MalformedNativeResponseError(
                f"prompted-mode response from {self._base_url} was not the expected "
                "OpenAI-compatible shape"
            ) from exc
        return parse_prompted_response(content, known_tools=_tool_names(tools))

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
        "one or more JSON objects and nothing else (no prose, no markdown fences):",
        '- To call a tool: {"tool": "<name>", "args": {...}}',
        '- To give your final answer: {"final": "<answer text>"}',
        # D73: a multi-part question naturally wants more than one tool call in the same turn
        # (e.g. two independent searches) — the model previously had no legal way to say that
        # in one strict-JSON reply and would emit two objects anyway, which the parser used to
        # treat as unstructured text and leak verbatim to the user. Batching is now both
        # explicitly permitted here and actually parsed (see parse_prompted_response).
        "- If you need to call MORE than one tool this turn, put each call on its own line, one "
        'JSON object per line, e.g. {"tool": "a", "args": {}}\\n{"tool": "b", "args": {}} — '
        "never mix a tool call and a final answer in the same reply.",
        "Available tools:",
    ]
    for entry in tools:
        function = entry.get("function", entry)
        name = function.get("name", "")
        description = function.get("description", "")
        params = function.get("parameters", {})
        lines.append(f"- {name}: {description} — parameters JSON Schema: {json.dumps(params)}")
    return "\n".join(lines)


def _tool_names(tools: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    """The registered tool names out of ``complete_with_tools``'s ``tools`` param — shared by
    the instruction renderer above and :func:`parse_prompted_response`'s ``known_tools`` (D8)."""
    return frozenset(str(entry.get("function", entry).get("name", "")) for entry in tools)


def _strip_wrapping_fence(text: str) -> str:
    """Strip a code fence ONLY when a single ``` pair wraps the ENTIRE reply (D10, postmortem
    follow-up audit) — an interior fence (one that appears alongside other text, not as the
    reply's sole wrapper) is left completely untouched.

    The prior implementation (``_FENCE_RE``, ``re.MULTILINE``) stripped ANY line that merely
    STARTED or ENDED with a fence marker, anywhere in the reply — not just a pair that wrapped
    the whole thing. Reproduced against the real parser: a reply that legitimately explained
    something using an embedded fenced JSON example —
    ``'Example call:\\n```\\n{"tool": "search",\\n```\\n"args": {"k": 3}}'`` — had BOTH its
    interior fence markers deleted (one strips forward past its own line, the other strips
    backward past its own line), silently gluing the prose-adjacent fragments on either side
    into ``'{"tool": "search",\\n"args": {"k": 3}}'`` — a complete, parseable, and entirely
    FABRICATED tool call the model never actually asked for; it only ever wanted to show an
    example inline. ``re.fullmatch`` on the whole (stripped) reply means this only fires when
    the fence markers are the reply's own outermost delimiters, with nothing else outside them.
    """
    stripped = text.strip()
    match = _WRAPPING_FENCE_RE.fullmatch(stripped)
    return match.group(1).strip() if match else text


def _canonical_tool_name(raw: Any) -> str:
    """Normalise a tool name the model wrote so ``" Search "`` and ``"search"`` meet: prompted
    models drift in case and whitespace far more often than they invent a genuinely different
    name, and a call that names a real tool should run, not leak."""
    return str(raw).strip().casefold()


def _is_control_shaped(obj: Mapping[str, Any], known: Collection[str]) -> bool:
    """Whether a dict is a prompted-mode control message rather than a JSON answer that happens
    to contain a ``tool`` or ``final`` key.

    Third-pass audit finding: the first version demanded an EXACT key set (``{tool}``,
    ``{tool, args}``, ``{final}``), so ``{"tool": "search", "args": {...}, "reason": "look it
    up"}`` -- a REGISTERED tool plus one chatty extra key, ordinary model drift -- fell out and
    was streamed to the user verbatim: the original incident shape. The registry is the
    stronger signal and it is already in hand, so use it FIRST:

    * ``tool`` naming a registered tool (case/whitespace-insensitive) -> control message, no
      matter what else is in the object.
    * ``tool`` naming something unknown -> control message only if nothing but ``tool``/``args``
      is present (a broken call attempt); with other keys it is a JSON answer
      (``{"tool": "Jira", "owner": "IT"}``, D8).
    * ``final`` with a STRING value -> control message, extra keys or not (``{"final": "the
      answer", "note": "done"}`` was also leaking). A non-string ``final`` (``{"final": true,
      "score": 3}``) is an answer field, not a control message.
    """
    keys = set(obj)
    if "tool" in keys and _canonical_tool_name(obj["tool"]) in known:
        return True
    if "final" in keys:
        # Any value: a prompted model answering "list the documents" emits {"final": [...]}
        # and one answering "how many" emits {"final": 42} (fourth-pass audit); delivering the
        # raw envelope for those was a leak, so they are control messages and their value is
        # rendered by _final_value. A stray junk "tool" key next to a "final" changes nothing.
        return True
    return "tool" in keys and keys <= {"tool", "args"}


def _final_value(value: Any) -> str:
    """The user-facing text of a ``{"final": ...}``: a string as-is, anything else as compact
    JSON (a list of filenames, a number, a boolean) rather than the raw protocol envelope."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _deliver_prose(text: str) -> ToolCompletion:
    """The ONE exit for prose in prompted mode (fourth-pass audit): every branch that hands prose
    back goes through the same broken-control-message check, so a reply cannot smuggle a
    truncated or single-quoted control object out merely by ALSO containing something the
    earlier branches consumed (a quoted final followed by a truncated tool call was reproduced
    doing exactly that). Prose that fails to parse as JSON and carries the truncated/quoted
    signature is a broken control message; otherwise it is the answer, with the D42/D43 scrub.
    """
    stripped = text.strip()
    if not _parses_as_json(stripped) and (
        stripped.startswith("{") or TRUNCATED_PROTOCOL_RE.search(stripped)
    ):
        return ToolCompletion(content=text, malformed=True)
    return ToolCompletion(content=_strip_trailing_tool_json(text))


def _prose_outside(text: str, spans: Sequence[tuple[int, int]]) -> str:
    """The text of ``text`` that lies outside the given ``(start, end)`` spans, whitespace
    collapsed. Used to decide whether a ``{"final": ...}`` IS the reply or is merely quoted
    inside a real prose answer."""
    out: list[str] = []
    cursor = 0
    for a, b in sorted(spans):
        out.append(text[cursor:a])
        cursor = b
    out.append(text[cursor:])
    return " ".join("".join(out).split())


# Below this much surrounding text a ``{"final": ...}`` is simply the reply with some chatter
# ("Sure, here it is:") and its value is the answer, no further questions asked.
_FINAL_CHATTER_MAX_CHARS = 80


def _looks_like_a_quote(final_value: str, outside: str) -> bool:
    """Given a ``{"final"}`` object embedded in SUBSTANTIAL prose, is the object a quote inside
    a real answer (D7: documentation about the protocol itself) or is the prose the model's
    reasoning and the object the answer it was told to produce (the far more common shape from
    smaller prompted models)? A quote is short and dwarfed by the prose around it; an answer is
    not. Both thresholds are deliberately conservative: when in doubt the final wins, because
    losing a real answer is worse than dropping a stray quoted phrase from a docs answer, and
    neither outcome can leak protocol text.
    """
    return len(final_value) < 60 and len(final_value) < 0.2 * len(outside)


def parse_prompted_response(text: str, *, known_tools: Collection[str]) -> ToolCompletion:
    """Parse one prompted-mode reply into a :class:`~sift.core.types.ToolCompletion`.

    2026-08-18 live-demo postmortem, follow-up redesign (second pass after the Opus audit of the
    first). The ORIGINAL fix here sniffed shapes and was simultaneously too narrow (D2, D3) and
    too broad (D8). The first redesign decided by provenance but left three holes the audit
    reproduced end to end: two ``{"final"}`` objects leaked the first one verbatim, an object
    naming an UNREGISTERED tool leaked whole, and prose that merely quoted one ``{"final"}`` was
    replaced by that object's value. Each came from a gap between the branches. This version
    has no gap: every reply falls into exactly one of the outcomes below, in order.

    1. Strip a fence ONLY if it wraps the whole reply (:func:`_strip_wrapping_fence`, D10).
    2. Find every control object anywhere (:func:`~sift.core.toolprotocol.scan_protocol_objects`)
       and keep only those SHAPED like control messages (:func:`_is_control_shaped`), so a JSON
       answer with a stray ``tool`` key (D8) is never mistaken for one.
    3. Any control-shaped object naming a REGISTERED tool (case/whitespace-insensitive) is a
       real call: return ALL of them, prose on either side or not (D9). Calls win over finals.
    4. Any control-shaped object naming an UNKNOWN tool is a broken control message: the model
       tried to call something that does not exist (a hallucinated or misspelled tool). Return
       ``malformed=True`` so the caller nudges it with the real tool names, instead of either
       running nothing or showing the object to the user.
    5. Exactly one ``{"final": ...}`` that IS the reply (at most ``_FINAL_CHATTER_MAX_CHARS`` of
       anything else around it) is the answer. Two or more finals is a broken message
       (``malformed=True``): the model could not decide, and showing either verbatim is a leak.
    6. A ``{"final": ...}`` embedded in SUBSTANTIAL prose is a quote inside a real answer (D7 in
       prompted mode): the prose is the answer; the quoted object is removed from it so no
       protocol text reaches the user, and the rest is delivered intact.
    7. If nothing control-shaped parsed at all, the reply is a broken control message only when
       it fails to parse as JSON as a whole AND either starts with ``{`` or matches the
       truncated/single-quoted signature (D2, D3). A reply that parses as JSON but is not a
       control message (``{"wrapper": {"tool": ...}}``) is a JSON answer, not malformed.
    8. Otherwise this is a genuine prose answer, with the D42/D43 trailing-tool-args scrub.
    """
    working = _strip_wrapping_fence(text)
    if not working.strip():
        # A reply that is only a fence, or nothing at all: not an answer, not a call. Nudge.
        return ToolCompletion(content=text, malformed=True)
    known = {_canonical_tool_name(name) for name in known_tools}
    found = [
        (obj, span)
        for obj, span in scan_protocol_objects(working, with_spans=True)
        if _is_control_shaped(obj, known)
    ]

    known_calls = [
        obj for obj, _ in found if "tool" in obj and _canonical_tool_name(obj["tool"]) in known
    ]
    if known_calls:
        others = [
            str(obj["tool"])
            for obj, _ in found
            if "tool" in obj and _canonical_tool_name(obj["tool"]) not in known
        ]
        if others:
            # Run what exists; the model sees only those results and can re-plan. Logged
            # rather than failed: a nudge here would discard real, useful calls.
            logger.warning(
                "prompted reply named unknown tool(s) %s alongside real ones; running the "
                "real ones only",
                sorted(set(others)),
            )
        return ToolCompletion(
            tool_calls=tuple(_tool_call_from_dict(obj, known_tools) for obj in known_calls)
        )

    finals = [(obj, span) for obj, span in found if "final" in obj]
    if not finals and found:
        # Only broken call attempts (unknown tool names): nudge with the real registry.
        return ToolCompletion(content=working, malformed=True)
    if len(finals) > 1:
        return ToolCompletion(content=working, malformed=True)
    if len(finals) == 1:
        obj, span = finals[0]
        value = _final_value(obj["final"])
        outside = _prose_outside(working, [span])
        if len(outside) <= _FINAL_CHATTER_MAX_CHARS or not _looks_like_a_quote(value, outside):
            # The final IS the reply: either only chatter surrounds it, or the prose is the
            # model's reasoning and the final is the answer it was told to produce.
            return ToolCompletion(content=value)
        # A short final inside long prose is ambiguous: a quote inside a real answer (D7) or a
        # short real answer ("Alice Martin", "Yes", a date) after the model's reasoning. Both
        # were common enough to reproduce, and each was being lost by favouring the other, so
        # deliver both: the prose with the protocol object excised, then the value. Nothing is
        # lost in either reading and no protocol text reaches the user.
        prose = (working[: span[0]] + working[span[1] :]).strip()
        delivered = _deliver_prose(prose)
        if delivered.malformed:
            return delivered
        return ToolCompletion(content=f"{delivered.content}\n\n{value}".strip())

    return _deliver_prose(working)


def _parses_as_json(text: str) -> bool:
    if not text.startswith(("{", "[")):
        return False
    try:
        json.loads(text)
    except (TypeError, ValueError, RecursionError):
        return False
    return True


def _tool_call_from_dict(obj: Mapping[str, Any], known_tools: Collection[str]) -> ToolCall:
    """Build one :class:`~sift.core.types.ToolCall` from a parsed ``{"tool": ..., "args": ...}``
    prompted-mode object — shared by the single-object and D73 multi-object parse paths above.
    Malformed ``args`` (not a JSON object) degrades to an empty-args call, same as the native
    parser's :func:`_parse_native_tool_call` handles malformed ``function.arguments``.
    """
    args = obj.get("args")
    wanted = _canonical_tool_name(obj["tool"])
    # Hand the registry the name it registered, not the model's casing/whitespace of it.
    name = next((t for t in known_tools if _canonical_tool_name(t) == wanted), str(obj["tool"]))
    return ToolCall(
        id=f"call_{uuid.uuid4().hex[:8]}",
        name=name,
        arguments=args if isinstance(args, dict) else {},
    )
