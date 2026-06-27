"""No-op Completer: echoes the user turn so the search pipeline can go green before a real
chat model lands. Selected when no ``LLM_BASE_URL`` is configured (README §7) — the recap is
just the best chunk's text, unsummarized.
"""

from __future__ import annotations


class NullCompleter:
    """Returns the ``user`` turn verbatim — no model, no summarization."""

    async def complete(self, system: str, user: str) -> str:
        return user
