"""No-op Completer: echoes the user turn so the search pipeline can go green before a real
chat model lands. Selected when no ``LLM_BASE_URL`` is configured (README §7) — the recap is
just the best chunk's text, unsummarized.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sift.core.types import ToolCompletion


class NullCompleter:
    """Returns the ``user`` turn verbatim — no model, no summarization.

    Also implements :class:`~sift.core.ports.ToolCompleter` (WP v0.2.0 T3) so ``factory.py``
    can wire ``Container.answer`` unconditionally, even with no ``LLM_BASE_URL`` configured:
    :meth:`complete_with_tools` never calls a tool and answers honestly that no model is
    configured, rather than the container failing to build at all.
    """

    async def complete(self, system: str, user: str) -> str:
        return user

    async def complete_with_tools(
        self, messages: Sequence[Mapping[str, Any]], tools: Sequence[Mapping[str, Any]]
    ) -> ToolCompletion:
        return ToolCompletion(content="No LLM is configured (LLM_BASE_URL unset) — cannot answer.")
