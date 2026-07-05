"""In-memory test double for the ``ConversationStore`` seam (``pipelines/answer.py``, D40).

Per-tenant dicts give tenant isolation for free, mirroring ``FakeVectorStore`` — the same
pattern this codebase already uses for every other store-shaped fake.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sift.core.types import ConversationDetail, ConversationMeta, ConversationTurn


class _Meta:
    """Mutable per-conversation metadata row — never exposed outside this module."""

    __slots__ = ("title", "created_at", "updated_at")

    def __init__(self, created_at: str) -> None:
        self.title: str | None = None
        self.created_at = created_at
        self.updated_at = created_at


class FakeConversationStore:
    """Keyed by ``(tenant, conversation_id)``; each value is its turns, oldest first.

    ``turn`` is a monotonic counter tracked independently of the list's length: once trimming
    has ever dropped the oldest turns, ``len(turns)`` under-counts the next ordinal to use, so
    a counter dict (never decremented) is the source of truth instead — mirrors
    ``LibSQLConversationStore``'s ``MAX(turn) + 1`` for the same reason.

    ``_meta`` (WP v0.2.0 T6, D42) is a sibling dict, same key shape, holding the
    title/created_at/updated_at row every conversation gets on its first ``append_turn``.
    """

    def __init__(self) -> None:
        self._turns: dict[tuple[str, str], list[ConversationTurn]] = {}
        self._next_turn: dict[tuple[str, str], int] = {}
        self._meta: dict[tuple[str, str], _Meta] = {}

    async def append_turn(
        self,
        tenant: str,
        conversation_id: str,
        role: str,
        content: str,
        *,
        max_turns: int,
        sources: list[dict] | None = None,
        grounding_used: str | None = None,
        from_general_knowledge: bool = False,
        grounding_segments: list[dict[str, str]] | None = None,
    ) -> None:
        key = (tenant, conversation_id)
        turns = self._turns.setdefault(key, [])
        turn = self._next_turn.get(key, 0)
        self._next_turn[key] = turn + 1
        now = datetime.now(UTC).isoformat()
        turns.append(
            ConversationTurn(
                role=role,
                content=content,
                turn=turn,
                created_at=now,
                sources=sources,
                grounding_used=grounding_used,
                from_general_knowledge=from_general_knowledge,
                grounding_segments=grounding_segments,
            )
        )
        if len(turns) > max_turns:
            del turns[: len(turns) - max_turns]
        meta = self._meta.get(key)
        if meta is None:
            self._meta[key] = _Meta(now)
        else:
            meta.updated_at = now

    async def history(self, tenant: str, conversation_id: str) -> list[ConversationTurn]:
        return list(self._turns.get((tenant, conversation_id), []))

    async def prune_expired(self, tenant: str, ttl_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
        stale = [
            key
            for key, turns in self._turns.items()
            if key[0] == tenant
            and turns
            and max(datetime.fromisoformat(t.created_at) for t in turns) < cutoff
        ]
        deleted = 0
        for key in stale:
            deleted += len(self._turns.pop(key))
            self._next_turn.pop(key, None)
            self._meta.pop(key, None)
        return deleted

    async def set_title_if_unset(self, tenant: str, conversation_id: str, title: str) -> None:
        meta = self._meta.get((tenant, conversation_id))
        if meta is not None and meta.title is None:
            meta.title = title

    def _meta_for(self, tenant: str, conversation_id: str) -> ConversationMeta | None:
        meta = self._meta.get((tenant, conversation_id))
        if meta is None:
            return None
        turn_count = len(self._turns.get((tenant, conversation_id), []))
        return ConversationMeta(
            conversation_id=conversation_id,
            title=meta.title,
            created_at=meta.created_at,
            updated_at=meta.updated_at,
            turn_count=turn_count,
        )

    async def list_conversations(
        self, tenant: str, *, limit: int, offset: int
    ) -> list[ConversationMeta]:
        metas = [
            meta
            for (t, conversation_id) in self._meta
            if t == tenant
            for meta in [self._meta_for(tenant, conversation_id)]
            if meta is not None
        ]
        metas.sort(key=lambda m: m.updated_at, reverse=True)
        return metas[offset : offset + limit]

    async def get_conversation(
        self, tenant: str, conversation_id: str
    ) -> ConversationDetail | None:
        meta = self._meta_for(tenant, conversation_id)
        if meta is None:
            return None
        return ConversationDetail(meta=meta, turns=await self.history(tenant, conversation_id))

    async def delete_conversation(self, tenant: str, conversation_id: str) -> None:
        key = (tenant, conversation_id)
        self._turns.pop(key, None)
        self._next_turn.pop(key, None)
        self._meta.pop(key, None)
