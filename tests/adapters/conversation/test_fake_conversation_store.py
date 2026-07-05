"""Tests for :class:`~sift.adapters.conversation.fake.FakeConversationStore` (WP v0.2.0 T3, D40)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sift.adapters.conversation.fake import FakeConversationStore

TENANT = "default"


async def test_append_and_history_round_trip_oldest_first() -> None:
    store = FakeConversationStore()

    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20)

    turns = await store.history(TENANT, "c1")

    assert [t.role for t in turns] == ["user", "assistant"]
    assert [t.content for t in turns] == ["hi", "hello"]
    assert [t.turn for t in turns] == [0, 1]


async def test_history_is_empty_for_unknown_conversation() -> None:
    store = FakeConversationStore()

    assert await store.history(TENANT, "does-not-exist") == []


async def test_append_turn_trims_to_max_turns() -> None:
    store = FakeConversationStore()

    for i in range(5):
        await store.append_turn(TENANT, "c1", "user", f"turn {i}", max_turns=3)

    turns = await store.history(TENANT, "c1")

    assert [t.content for t in turns] == ["turn 2", "turn 3", "turn 4"]
    assert [t.turn for t in turns] == [2, 3, 4]  # turn ordinals aren't renumbered on trim


async def test_tenants_are_isolated() -> None:
    store = FakeConversationStore()

    await store.append_turn("tenant-a", "c1", "user", "a's message", max_turns=20)
    await store.append_turn("tenant-b", "c1", "user", "b's message", max_turns=20)

    a_turns = await store.history("tenant-a", "c1")
    b_turns = await store.history("tenant-b", "c1")

    assert [t.content for t in a_turns] == ["a's message"]
    assert [t.content for t in b_turns] == ["b's message"]


async def test_prune_expired_deletes_stale_conversations() -> None:
    store = FakeConversationStore()
    await store.append_turn(TENANT, "stale", "user", "old", max_turns=20)
    # Backdate the turn's created_at so it looks 40 days old.
    key = (TENANT, "stale")
    old_turn = store._turns[key][0]
    stale_time = datetime.now(UTC) - timedelta(days=40)
    store._turns[key][0] = old_turn.__class__(
        role=old_turn.role,
        content=old_turn.content,
        turn=old_turn.turn,
        created_at=stale_time.isoformat(),
    )
    await store.append_turn(TENANT, "fresh", "user", "new", max_turns=20)

    deleted = await store.prune_expired(TENANT, ttl_days=30)

    assert deleted == 1
    assert await store.history(TENANT, "stale") == []
    assert len(await store.history(TENANT, "fresh")) == 1


# --- conversation metadata: title/updated_at/listing/get/delete (WP v0.2.0 T6, D42) ----------


async def test_append_turn_creates_meta_row_with_no_title() -> None:
    store = FakeConversationStore()

    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)

    (meta,) = await store.list_conversations(TENANT, limit=10, offset=0)
    assert meta.conversation_id == "c1"
    assert meta.title is None
    assert meta.turn_count == 1
    assert meta.created_at and meta.updated_at


async def test_append_turn_bumps_updated_at_on_every_turn() -> None:
    store = FakeConversationStore()

    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    (meta_after_first,) = await store.list_conversations(TENANT, limit=10, offset=0)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20)
    (meta_after_second,) = await store.list_conversations(TENANT, limit=10, offset=0)

    assert meta_after_second.updated_at >= meta_after_first.updated_at
    assert meta_after_second.turn_count == 2


async def test_append_turn_persists_sources_on_that_turn_only() -> None:
    store = FakeConversationStore()
    sources = [{"path": "a.md", "page": 1, "score": 0.9, "snippet": "hi"}]

    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20, sources=sources)

    turns = await store.history(TENANT, "c1")
    assert turns[0].sources is None
    assert turns[1].sources == sources


async def test_append_turn_persists_grounding_fields_on_that_turn_only() -> None:
    """D51 — the per-turn immutable grounding fields, same pattern as ``sources`` above."""
    store = FakeConversationStore()
    segments = [{"text": "hello", "kind": "grounded"}]

    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    await store.append_turn(
        TENANT,
        "c1",
        "assistant",
        "hello",
        max_turns=20,
        grounding_used="strict",
        from_general_knowledge=False,
        grounding_segments=segments,
    )

    turns = await store.history(TENANT, "c1")
    assert turns[0].grounding_used is None
    assert turns[0].from_general_knowledge is False
    assert turns[0].grounding_segments is None
    assert turns[1].grounding_used == "strict"
    assert turns[1].from_general_knowledge is False
    assert turns[1].grounding_segments == segments


async def test_list_conversations_orders_by_updated_at_desc() -> None:
    store = FakeConversationStore()
    await store.append_turn(TENANT, "older", "user", "a", max_turns=20)
    await store.append_turn(TENANT, "newer", "user", "b", max_turns=20)

    metas = await store.list_conversations(TENANT, limit=10, offset=0)

    assert [m.conversation_id for m in metas] == ["newer", "older"]


async def test_list_conversations_respects_limit_and_offset() -> None:
    store = FakeConversationStore()
    for i in range(5):
        await store.append_turn(TENANT, f"c{i}", "user", "hi", max_turns=20)

    page = await store.list_conversations(TENANT, limit=2, offset=1)

    assert len(page) == 2


async def test_list_conversations_tenants_are_isolated() -> None:
    store = FakeConversationStore()
    await store.append_turn("tenant-a", "c1", "user", "a", max_turns=20)
    await store.append_turn("tenant-b", "c1", "user", "b", max_turns=20)

    a_metas = await store.list_conversations("tenant-a", limit=10, offset=0)
    b_metas = await store.list_conversations("tenant-b", limit=10, offset=0)

    assert [m.conversation_id for m in a_metas] == ["c1"]
    assert [m.conversation_id for m in b_metas] == ["c1"]


async def test_get_conversation_returns_meta_and_turns() -> None:
    store = FakeConversationStore()
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20)

    detail = await store.get_conversation(TENANT, "c1")

    assert detail is not None
    assert detail.meta.conversation_id == "c1"
    assert detail.meta.turn_count == 2
    assert [t.content for t in detail.turns] == ["hi", "hello"]


async def test_get_conversation_returns_none_for_unknown() -> None:
    store = FakeConversationStore()

    assert await store.get_conversation(TENANT, "does-not-exist") is None


async def test_get_conversation_respects_tenant() -> None:
    store = FakeConversationStore()
    await store.append_turn("tenant-a", "c1", "user", "a's message", max_turns=20)

    assert await store.get_conversation("tenant-b", "c1") is None
    assert await store.get_conversation("tenant-a", "c1") is not None


async def test_delete_conversation_removes_turns_and_meta() -> None:
    store = FakeConversationStore()
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)

    await store.delete_conversation(TENANT, "c1")

    assert await store.history(TENANT, "c1") == []
    assert await store.get_conversation(TENANT, "c1") is None
    assert await store.list_conversations(TENANT, limit=10, offset=0) == []


async def test_delete_conversation_is_idempotent() -> None:
    store = FakeConversationStore()

    await store.delete_conversation(TENANT, "does-not-exist")  # must not raise
    await store.delete_conversation(TENANT, "does-not-exist")


async def test_set_title_if_unset_sets_title_once() -> None:
    store = FakeConversationStore()
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)

    await store.set_title_if_unset(TENANT, "c1", "First title")
    await store.set_title_if_unset(TENANT, "c1", "Second title")  # never regenerated

    detail = await store.get_conversation(TENANT, "c1")
    assert detail is not None
    assert detail.meta.title == "First title"
