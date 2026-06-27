"""LLM-as-judge reranker — asks a chat model to pick the single most relevant candidate.

Implements the :class:`~sift.core.ports.Reranker` port via a :class:`~sift.core.ports.Completer`:
build a numbered list of the first ``max_candidates`` hits (index, source path, text snippet), ask
the model for ONLY the index of the best one, parse the first integer robustly (clamp to range,
default 0 on failure), and return the candidates with that hit moved to the front. The rest keep
their original order — the search pipeline only needs the top-1, so a coarse "best first" reorder
is enough and the scores are left untouched (no cross-encoder number to assign).
"""

from __future__ import annotations

import re

from sift.core.ports import Completer
from sift.core.types import Hit

_SNIPPET_LEN = 240

_SYSTEM = (
    "You are a search reranker. Given a query and a numbered list of candidate passages, "
    "reply with ONLY the integer index of the single most relevant passage — no other text."
)


class LlmJudgeReranker:
    """Reranker that delegates the top-1 choice to a chat Completer."""

    def __init__(self, completer: Completer, max_candidates: int = 12) -> None:
        self._completer = completer
        self._max_candidates = max_candidates

    async def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]:
        if not candidates:
            return []
        considered = candidates[: self._max_candidates]
        reply = await self._completer.complete(_SYSTEM, self._build_user(query, considered))
        chosen = self._parse_index(reply, len(considered))
        return [candidates[chosen], *candidates[:chosen], *candidates[chosen + 1 :]]

    @staticmethod
    def _build_user(query: str, considered: list[Hit]) -> str:
        lines = [f"Query: {query}", "", "Candidates:"]
        for index, hit in enumerate(considered):
            snippet = " ".join(hit.text.split())[:_SNIPPET_LEN]
            lines.append(f"[{index}] ({hit.source_path}) {snippet}")
        lines.append("")
        lines.append("Reply with only the index of the most relevant candidate.")
        return "\n".join(lines)

    @staticmethod
    def _parse_index(reply: str, count: int) -> int:
        match = re.search(r"\d+", reply)
        if match is None:
            return 0
        return min(int(match.group()), count - 1)
