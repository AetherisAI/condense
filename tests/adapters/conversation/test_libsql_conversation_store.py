"""Tests for :class:`~sift.adapters.conversation.libsql.LibSQLConversationStore` (WP v0.2.0 T3,
D40) — parity with ``FakeConversationStore`` against a real ``tmp_path`` libSQL DB.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

libsql = pytest.importorskip("libsql")

from sift.adapters.conversation.libsql import LibSQLConversationStore  # noqa: E402

TENANT = "default"


@pytest.fixture
async def store(tmp_path) -> AsyncIterator[LibSQLConversationStore]:
    impl = LibSQLConversationStore(str(tmp_path / "conversations.db"))
    try:
        yield impl
    finally:
        await impl.aclose()


@pytest.fixture
def db_path(tmp_path) -> str:
    return str(tmp_path / "conversations.db")


async def test_history_is_empty_before_any_append(store: LibSQLConversationStore) -> None:
    assert await store.history(TENANT, "does-not-exist") == []


async def test_append_and_history_round_trip_oldest_first(store: LibSQLConversationStore) -> None:
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20)

    turns = await store.history(TENANT, "c1")

    assert [t.role for t in turns] == ["user", "assistant"]
    assert [t.content for t in turns] == ["hi", "hello"]
    assert [t.turn for t in turns] == [0, 1]


async def test_append_turn_trims_to_max_turns(store: LibSQLConversationStore) -> None:
    for i in range(5):
        await store.append_turn(TENANT, "c1", "user", f"turn {i}", max_turns=3)

    turns = await store.history(TENANT, "c1")

    assert [t.content for t in turns] == ["turn 2", "turn 3", "turn 4"]
    assert [t.turn for t in turns] == [2, 3, 4]  # turn ordinals aren't renumbered on trim


async def test_tenants_are_isolated(store: LibSQLConversationStore) -> None:
    await store.append_turn("tenant-a", "c1", "user", "a's message", max_turns=20)
    await store.append_turn("tenant-b", "c1", "user", "b's message", max_turns=20)

    a_turns = await store.history("tenant-a", "c1")
    b_turns = await store.history("tenant-b", "c1")

    assert [t.content for t in a_turns] == ["a's message"]
    assert [t.content for t in b_turns] == ["b's message"]


async def test_prune_expired_deletes_stale_conversations(db_path: str) -> None:
    # Deliberately does NOT use the `store` fixture: this test closes its store mid-test (to
    # release the connection before a second one touches the same file), which would double
    # `aclose()` the fixture's own teardown otherwise.
    store = LibSQLConversationStore(db_path)
    await store.append_turn(TENANT, "stale", "user", "old", max_turns=20)
    await store.aclose()  # release the store's own connection before a second one touches the file

    stale_time = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    conn = libsql.connect(db_path)
    conn.execute(
        "UPDATE conversations SET created_at = ? WHERE tenant = ? AND conversation_id = ?",
        (stale_time, TENANT, "stale"),
    )
    conn.commit()
    conn.close()

    store2 = LibSQLConversationStore(db_path)
    try:
        await store2.append_turn(TENANT, "fresh", "user", "new", max_turns=20)

        deleted = await store2.prune_expired(TENANT, ttl_days=30)

        assert deleted == 1
        assert await store2.history(TENANT, "stale") == []
        assert len(await store2.history(TENANT, "fresh")) == 1
    finally:
        await store2.aclose()


async def test_append_turn_rejects_non_str_content_with_clear_type_error(
    store: LibSQLConversationStore,
) -> None:
    # D40 amendment (BUG #2 defense-in-depth): a non-str `content` (e.g. an un-normalized
    # provider content-block list slipping past the adapter) must fail LOUD and EARLY with a
    # clear TypeError, never as an opaque libsql "ValueError: Unsupported parameter type" from
    # deep inside the DB bind.
    bad_content: str = [{"type": "text", "text": "oops"}]  # type: ignore[assignment]
    with pytest.raises(TypeError, match="content must be str"):
        await store.append_turn(TENANT, "c1", "assistant", bad_content, max_turns=20)


async def test_prune_expired_on_fresh_db_returns_zero(tmp_path) -> None:
    impl = LibSQLConversationStore(str(tmp_path / "fresh.db"))
    try:
        assert await impl.prune_expired(TENANT, ttl_days=30) == 0
    finally:
        await impl.aclose()


# --- conversation metadata: title/updated_at/listing/get/delete (WP v0.2.0 T6, D42) ----------


async def test_append_turn_creates_meta_row_with_no_title(store: LibSQLConversationStore) -> None:
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)

    (meta,) = await store.list_conversations(TENANT, limit=10, offset=0)
    assert meta.conversation_id == "c1"
    assert meta.title is None
    assert meta.turn_count == 1
    assert meta.created_at and meta.updated_at


async def test_append_turn_bumps_updated_at_on_every_turn(store: LibSQLConversationStore) -> None:
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    (meta_after_first,) = await store.list_conversations(TENANT, limit=10, offset=0)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20)
    (meta_after_second,) = await store.list_conversations(TENANT, limit=10, offset=0)

    assert meta_after_second.updated_at >= meta_after_first.updated_at
    assert meta_after_second.turn_count == 2


async def test_append_turn_persists_grounding_fields_on_that_turn_only(
    store: LibSQLConversationStore,
) -> None:
    """D51 — the per-turn immutable grounding fields, same pattern as ``sources`` below."""
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


async def test_append_turn_persists_sources_on_that_turn_only(
    store: LibSQLConversationStore,
) -> None:
    sources = [{"path": "a.md", "page": 1, "score": 0.9, "snippet": "hi"}]

    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20, sources=sources)

    turns = await store.history(TENANT, "c1")
    assert turns[0].sources is None
    assert turns[1].sources == sources


async def test_list_conversations_orders_by_updated_at_desc(
    store: LibSQLConversationStore,
) -> None:
    await store.append_turn(TENANT, "older", "user", "a", max_turns=20)
    await store.append_turn(TENANT, "newer", "user", "b", max_turns=20)

    metas = await store.list_conversations(TENANT, limit=10, offset=0)

    assert [m.conversation_id for m in metas] == ["newer", "older"]


async def test_list_conversations_respects_limit_and_offset(
    store: LibSQLConversationStore,
) -> None:
    for i in range(5):
        await store.append_turn(TENANT, f"c{i}", "user", "hi", max_turns=20)

    page = await store.list_conversations(TENANT, limit=2, offset=1)

    assert len(page) == 2


async def test_list_conversations_tenants_are_isolated(store: LibSQLConversationStore) -> None:
    await store.append_turn("tenant-a", "c1", "user", "a", max_turns=20)
    await store.append_turn("tenant-b", "c1", "user", "b", max_turns=20)

    a_metas = await store.list_conversations("tenant-a", limit=10, offset=0)
    b_metas = await store.list_conversations("tenant-b", limit=10, offset=0)

    assert [m.conversation_id for m in a_metas] == ["c1"]
    assert [m.conversation_id for m in b_metas] == ["c1"]


async def test_list_conversations_on_fresh_db_returns_empty(tmp_path) -> None:
    impl = LibSQLConversationStore(str(tmp_path / "fresh.db"))
    try:
        assert await impl.list_conversations(TENANT, limit=10, offset=0) == []
    finally:
        await impl.aclose()


async def test_get_conversation_returns_meta_and_turns(store: LibSQLConversationStore) -> None:
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)
    await store.append_turn(TENANT, "c1", "assistant", "hello", max_turns=20)

    detail = await store.get_conversation(TENANT, "c1")

    assert detail is not None
    assert detail.meta.conversation_id == "c1"
    assert detail.meta.turn_count == 2
    assert [t.content for t in detail.turns] == ["hi", "hello"]


async def test_get_conversation_returns_none_for_unknown(store: LibSQLConversationStore) -> None:
    assert await store.get_conversation(TENANT, "does-not-exist") is None


async def test_get_conversation_on_fresh_db_returns_none(tmp_path) -> None:
    impl = LibSQLConversationStore(str(tmp_path / "fresh.db"))
    try:
        assert await impl.get_conversation(TENANT, "c1") is None
    finally:
        await impl.aclose()


async def test_delete_conversation_removes_turns_and_meta(store: LibSQLConversationStore) -> None:
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)

    await store.delete_conversation(TENANT, "c1")

    assert await store.history(TENANT, "c1") == []
    assert await store.get_conversation(TENANT, "c1") is None
    assert await store.list_conversations(TENANT, limit=10, offset=0) == []


async def test_delete_conversation_is_idempotent(store: LibSQLConversationStore) -> None:
    await store.delete_conversation(TENANT, "does-not-exist")  # must not raise
    await store.delete_conversation(TENANT, "does-not-exist")


async def test_set_title_if_unset_sets_title_once(store: LibSQLConversationStore) -> None:
    await store.append_turn(TENANT, "c1", "user", "hi", max_turns=20)

    await store.set_title_if_unset(TENANT, "c1", "First title")
    await store.set_title_if_unset(TENANT, "c1", "Second title")  # never regenerated

    detail = await store.get_conversation(TENANT, "c1")
    assert detail is not None
    assert detail.meta.title == "First title"


async def test_legacy_db_missing_sources_column_migrates_on_read(db_path: str) -> None:
    """A ``conversations`` table predating the ``sources`` column (WP v0.2.0 T6, D42) must
    migrate (ALTER-if-missing) rather than 500 on the first read against it — same guard shape
    as the store's own ``files.modified_at``/``chunks.metadata`` migrations."""
    conn = libsql.connect(db_path)
    conn.execute(
        "CREATE TABLE conversations (tenant TEXT, conversation_id TEXT, turn INTEGER, "
        "role TEXT, content TEXT, created_at TEXT, PRIMARY KEY (tenant, conversation_id, turn))"
    )
    conn.execute(
        "INSERT INTO conversations VALUES ('default', 'legacy', 0, 'user', 'hi', '2020-01-01')"
    )
    conn.commit()
    conn.close()

    store = LibSQLConversationStore(db_path)
    try:
        turns = await store.history(TENANT, "legacy")
        assert [t.content for t in turns] == ["hi"]
        assert turns[0].sources is None

        detail = await store.get_conversation(TENANT, "legacy")
        assert detail is not None
        assert detail.meta.turn_count == 1
    finally:
        await store.aclose()


async def test_legacy_db_missing_grounding_columns_migrates_on_read(db_path: str) -> None:
    """A ``conversations`` table predating the D51 grounding columns must migrate (ALTER-if-
    missing) rather than 500 on the first read — same guard shape as the ``sources`` migration
    above, run one column further back (before ``sources`` even existed, the harshest case)."""
    conn = libsql.connect(db_path)
    conn.execute(
        "CREATE TABLE conversations (tenant TEXT, conversation_id TEXT, turn INTEGER, "
        "role TEXT, content TEXT, created_at TEXT, PRIMARY KEY (tenant, conversation_id, turn))"
    )
    conn.execute(
        "INSERT INTO conversations VALUES ('default', 'legacy', 0, 'user', 'hi', '2020-01-01')"
    )
    conn.commit()
    conn.close()

    store = LibSQLConversationStore(db_path)
    try:
        turns = await store.history(TENANT, "legacy")
        assert [t.content for t in turns] == ["hi"]
        assert turns[0].grounding_used is None
        assert turns[0].from_general_knowledge is False
        assert turns[0].grounding_segments is None

        # A fresh append_turn against this migrated table must still work end-to-end.
        await store.append_turn(
            TENANT,
            "legacy",
            "assistant",
            "hello",
            max_turns=20,
            grounding_used="hybrid",
            from_general_knowledge=True,
            grounding_segments=[{"text": "hello", "kind": "general_knowledge"}],
        )
        turns = await store.history(TENANT, "legacy")
        assert turns[1].grounding_used == "hybrid"
        assert turns[1].from_general_knowledge is True
    finally:
        await store.aclose()
