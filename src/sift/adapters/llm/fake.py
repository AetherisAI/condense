"""Scripted test double for the :class:`~sift.core.ports.ToolCompleter` port (WP v0.2.0 T3).

No network, fully deterministic — the hard rule for this WP is "no live LLM calls anywhere in
the automated suite"; every ``pipelines/answer.py`` test drives this instead of a real model.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sift.core.types import ToolCompletion

_Script = ToolCompletion | Callable[[Sequence[Mapping[str, Any]]], ToolCompletion]


class FakeToolCompleter:
    """Returns one scripted :class:`~sift.core.types.ToolCompletion` per call, in order.

    ``script`` entries are consumed one per :meth:`complete_with_tools` call; once exhausted,
    the LAST entry repeats forever — so a "the model loops forever" budget test needs only one
    scripted tool-call entry, not one per iteration the budget might allow. An entry may be a
    plain :class:`~sift.core.types.ToolCompletion` or a callable of the current ``messages``
    (for a response that depends on what's already in the transcript, e.g. the follow-up
    conversation-history test). ``delay_s`` optionally sleeps before returning, driving the
    ``answer_timeout_s`` budget test without a real slow backend. Every call's ``messages`` is
    recorded on :attr:`calls` for tests to assert on (e.g. "the second turn's messages contain
    the first turn's answer").
    """

    def __init__(self, script: Sequence[_Script], *, delay_s: float = 0.0) -> None:
        if not script:
            raise ValueError("FakeToolCompleter needs at least one scripted response")
        self._script = list(script)
        self._delay_s = delay_s
        self._calls: list[list[Mapping[str, Any]]] = []

    @property
    def calls(self) -> list[list[Mapping[str, Any]]]:
        """Every call's ``messages``, in order — a snapshot, not a live view."""
        return list(self._calls)

    async def complete_with_tools(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> ToolCompletion:
        recorded = list(messages)
        self._calls.append(recorded)
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        entry = self._script[min(len(self._calls) - 1, len(self._script) - 1)]
        return entry(recorded) if callable(entry) else entry


class FakeCompleter:
    """Scripted test double for the plain :class:`~sift.core.ports.Completer` port
    (``complete(system, user) -> str``) — used to drive the auto-title pass (WP v0.2.0 T6,
    D42) without a live LLM. ``raises`` lets a test exercise the "any failure falls back to
    the truncated first message" path with no real HTTP error to provoke.
    """

    def __init__(self, response: str = "", *, raises: bool = False) -> None:
        self._response = response
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    async def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self._raises:
            raise RuntimeError("boom")
        return self._response
