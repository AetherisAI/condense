"""libSQL/Turso-backed ``ConversationStore`` adapter (WP v0.2.0 T3, D40; extended T6, D42).

Same async-over-sync shape as :class:`~sift.adapters.store.libsql.LibSQLStore` (one connection,
touched only from a single-worker :class:`~concurrent.futures.ThreadPoolExecutor`) but against
its own connection to the same database file/URL — the conversation state is logically a
sibling table (``conversations``), not something that needs the vector store's internals.
Turn numbers are a monotonically increasing counter per ``(tenant, conversation_id)`` — derived
from ``MAX(turn) + 1``, NOT ``COUNT(*)``: once the ring-buffer trim below has ever dropped the
oldest rows, ``COUNT(*)`` under-counts the next ordinal to use and collides with a surviving
row's ``turn`` (the table's own primary key). ``MAX(turn)`` never goes backwards, so it stays
correct across any number of trims, and the trim itself stays a single ``turn < ?`` delete
rather than an ``ORDER BY``-based one.

T6 (D42) adds a sibling ``conversations_meta`` table (title/created_at/updated_at, one row per
``(tenant, conversation_id)``) and an additive ``sources`` column on ``conversations`` (per-turn
compact citations, JSON-encoded, set only on a citing assistant turn) — both migrated
ALTER-if-missing for a database created before them, mirroring ``LibSQLStore``'s own
``files.modified_at``/``chunks.metadata`` migration pattern. Every job (read or write) runs
``_ensure_schema`` first, so a fresh process's very first call — read or write — never 500s
against a not-yet-migrated file.

D51 adds three more additive columns, same ALTER-if-missing pattern: ``grounding_used`` (TEXT),
``from_general_knowledge`` (INTEGER 0/1), ``grounding_segments`` (TEXT, JSON) — the per-turn
immutable grounding a reopened conversation renders from, instead of resetting every historical
turn's marking to "unknown" on every reload (the actual root cause behind the purple
general-knowledge marking appearing to vanish after a tab switch or page refresh).
"""

from __future__ import annotations

import asyncio
import functools
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import libsql

from sift.core.types import ConversationDetail, ConversationMeta, ConversationTurn

_libsql: Any = libsql

_DDL_CONVERSATIONS = (
    "CREATE TABLE IF NOT EXISTS conversations ("
    "tenant TEXT, conversation_id TEXT, turn INTEGER, role TEXT, content TEXT, created_at TEXT, "
    "sources TEXT, "
    "PRIMARY KEY (tenant, conversation_id, turn))"
)

# Additive migration for databases created before `sources` existed — same ALTER-if-missing
# pattern as `LibSQLStore`'s `files.modified_at`/`chunks.metadata` (D28).
_CONVERSATIONS_HAS_SOURCES = (
    "SELECT 1 FROM pragma_table_info('conversations') WHERE name = 'sources'"
)
_ALTER_CONVERSATIONS_ADD_SOURCES = "ALTER TABLE conversations ADD COLUMN sources TEXT"

# Additive migration (D51) for the per-turn immutable grounding fields — same ALTER-if-missing
# pattern as `sources` above.
_CONVERSATIONS_HAS_GROUNDING_USED = (
    "SELECT 1 FROM pragma_table_info('conversations') WHERE name = 'grounding_used'"
)
_ALTER_CONVERSATIONS_ADD_GROUNDING_USED = "ALTER TABLE conversations ADD COLUMN grounding_used TEXT"
_CONVERSATIONS_HAS_FROM_GENERAL_KNOWLEDGE = (
    "SELECT 1 FROM pragma_table_info('conversations') WHERE name = 'from_general_knowledge'"
)
_ALTER_CONVERSATIONS_ADD_FROM_GENERAL_KNOWLEDGE = (
    "ALTER TABLE conversations ADD COLUMN from_general_knowledge INTEGER"
)
_CONVERSATIONS_HAS_GROUNDING_SEGMENTS = (
    "SELECT 1 FROM pragma_table_info('conversations') WHERE name = 'grounding_segments'"
)
_ALTER_CONVERSATIONS_ADD_GROUNDING_SEGMENTS = (
    "ALTER TABLE conversations ADD COLUMN grounding_segments TEXT"
)

_DDL_CONVERSATIONS_META = (
    "CREATE TABLE IF NOT EXISTS conversations_meta ("
    "tenant TEXT, conversation_id TEXT, title TEXT, created_at TEXT, updated_at TEXT, "
    "PRIMARY KEY (tenant, conversation_id))"
)

_UPSERT_META = (
    "INSERT INTO conversations_meta (tenant, conversation_id, title, created_at, updated_at) "
    "VALUES (?, ?, NULL, ?, ?) "
    "ON CONFLICT(tenant, conversation_id) DO UPDATE SET updated_at = excluded.updated_at"
)

_MAX_TURN = "SELECT MAX(turn) FROM conversations WHERE tenant = ? AND conversation_id = ?"

_INSERT_TURN = (
    "INSERT INTO conversations (tenant, conversation_id, turn, role, content, created_at, "
    "sources, grounding_used, from_general_knowledge, grounding_segments) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

_DELETE_OLD_TURNS = (
    "DELETE FROM conversations WHERE tenant = ? AND conversation_id = ? AND turn < ?"
)

_SELECT_HISTORY = (
    "SELECT role, content, turn, created_at, sources, grounding_used, from_general_knowledge, "
    "grounding_segments FROM conversations "
    "WHERE tenant = ? AND conversation_id = ? ORDER BY turn ASC"
)

_SELECT_STALE_CONVERSATION_IDS = (
    "SELECT conversation_id FROM conversations WHERE tenant = ? "
    "GROUP BY conversation_id HAVING MAX(created_at) < ?"
)

_DELETE_CONVERSATION = "DELETE FROM conversations WHERE tenant = ? AND conversation_id = ?"
_DELETE_CONVERSATION_META = (
    "DELETE FROM conversations_meta WHERE tenant = ? AND conversation_id = ?"
)

_SELECT_META = (
    "SELECT title, created_at, updated_at FROM conversations_meta "
    "WHERE tenant = ? AND conversation_id = ?"
)

_SELECT_META_LIST = (
    "SELECT m.conversation_id, m.title, m.created_at, m.updated_at, "
    "COUNT(c.turn) AS turn_count "
    "FROM conversations_meta m LEFT JOIN conversations c "
    "ON c.tenant = m.tenant AND c.conversation_id = m.conversation_id "
    "WHERE m.tenant = ? "
    "GROUP BY m.tenant, m.conversation_id, m.title, m.created_at, m.updated_at "
    "ORDER BY m.updated_at DESC LIMIT ? OFFSET ?"
)

_UPDATE_TITLE_IF_UNSET = (
    "UPDATE conversations_meta SET title = ? "
    "WHERE tenant = ? AND conversation_id = ? AND title IS NULL"
)


def _dump_sources(sources: list[dict[str, Any]] | None) -> str | None:
    return None if sources is None else json.dumps(sources)


def _load_sources(raw: str | None) -> list[dict[str, Any]] | None:
    return None if raw is None else json.loads(raw)


def _dump_grounding_segments(segments: list[dict[str, str]] | None) -> str | None:
    return None if segments is None else json.dumps(segments)


def _load_grounding_segments(raw: str | None) -> list[dict[str, str]] | None:
    return None if raw is None else json.loads(raw)


class LibSQLConversationStore:
    """``ConversationStore`` over a local-file or Turso libSQL database."""

    def __init__(self, database: str, *, auth_token: str | None = None) -> None:
        self._database = database
        self._auth_token = auth_token
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = asyncio.Lock()
        self._conn: Any = None
        self._migrated = False  # schema reconciled once per process (see `_ensure_schema`)

    def _connection(self) -> Any:
        if self._conn is None:
            if self._auth_token is not None:
                self._conn = _libsql.connect(self._database, auth_token=self._auth_token)
            else:
                self._conn = _libsql.connect(self._database)
        return self._conn

    async def _submit[T](self, job: Callable[[], T]) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, job)

    async def append_turn(
        self,
        tenant: str,
        conversation_id: str,
        role: str,
        content: str,
        *,
        max_turns: int,
        sources: list[dict[str, Any]] | None = None,
        grounding_used: str | None = None,
        from_general_knowledge: bool = False,
        grounding_segments: list[dict[str, str]] | None = None,
    ) -> None:
        # Defense-in-depth (D40 amendment, BUG #2): fail loud and early with a clear TypeError
        # rather than let a non-str `content` (e.g. an un-normalized provider content-block list
        # that slipped past the completer adapter) reach the DB bind, where libsql raises an
        # opaque ``ValueError: Unsupported parameter type`` far from the real cause.
        if not isinstance(content, str):
            raise TypeError(f"content must be str, got {type(content).__name__}: {content!r}")
        async with self._lock:
            await self._submit(
                functools.partial(
                    self._append_turn_job,
                    tenant,
                    conversation_id,
                    role,
                    content,
                    max_turns,
                    sources,
                    grounding_used,
                    from_general_knowledge,
                    grounding_segments,
                )
            )

    async def history(self, tenant: str, conversation_id: str) -> list[ConversationTurn]:
        return await self._submit(functools.partial(self._history_job, tenant, conversation_id))

    async def prune_expired(self, tenant: str, ttl_days: int) -> int:
        async with self._lock:
            return await self._submit(functools.partial(self._prune_expired_job, tenant, ttl_days))

    async def set_title_if_unset(self, tenant: str, conversation_id: str, title: str) -> None:
        async with self._lock:
            await self._submit(
                functools.partial(self._set_title_if_unset_job, tenant, conversation_id, title)
            )

    async def list_conversations(
        self, tenant: str, *, limit: int, offset: int
    ) -> list[ConversationMeta]:
        return await self._submit(
            functools.partial(self._list_conversations_job, tenant, limit, offset)
        )

    async def get_conversation(
        self, tenant: str, conversation_id: str
    ) -> ConversationDetail | None:
        return await self._submit(
            functools.partial(self._get_conversation_job, tenant, conversation_id)
        )

    async def delete_conversation(self, tenant: str, conversation_id: str) -> None:
        async with self._lock:
            await self._submit(
                functools.partial(self._delete_conversation_job, tenant, conversation_id)
            )

    async def aclose(self) -> None:
        await self._submit(self._close_job)
        self._executor.shutdown(wait=True)

    # --- executor jobs (run on the single worker thread) --------------------------

    def _ensure_schema(self, conn: Any) -> None:
        """Create-if-missing every table, ALTER-if-missing every additive column — run at the
        top of EVERY job (read or write) so a fresh process's first call, whichever it is,
        never 500s against a not-yet-migrated database (mirrors the BUG #1 fix in
        ``pipelines/tools.py``'s executors).

        The reconciliation is idempotent and can never change once done, so it runs at most once
        per process: after the first successful pass ``_migrated`` short-circuits every later
        call. All jobs are serialized on the single-worker executor over one long-lived
        connection, so the flag is race-free. This turns the ~6 create/probe statements that
        previously fired on *every* job (~24 per chat turn against remote Turso) into a one-time
        cost, and collapses the double-migrate in ``_get_conversation_job`` → ``_history_job``."""
        if self._migrated:
            return
        conn.execute(_DDL_CONVERSATIONS)
        if not conn.execute(_CONVERSATIONS_HAS_SOURCES).fetchall():
            conn.execute(_ALTER_CONVERSATIONS_ADD_SOURCES)
        if not conn.execute(_CONVERSATIONS_HAS_GROUNDING_USED).fetchall():
            conn.execute(_ALTER_CONVERSATIONS_ADD_GROUNDING_USED)
        if not conn.execute(_CONVERSATIONS_HAS_FROM_GENERAL_KNOWLEDGE).fetchall():
            conn.execute(_ALTER_CONVERSATIONS_ADD_FROM_GENERAL_KNOWLEDGE)
        if not conn.execute(_CONVERSATIONS_HAS_GROUNDING_SEGMENTS).fetchall():
            conn.execute(_ALTER_CONVERSATIONS_ADD_GROUNDING_SEGMENTS)
        conn.execute(_DDL_CONVERSATIONS_META)
        self._migrated = True

    def _append_turn_job(
        self,
        tenant: str,
        conversation_id: str,
        role: str,
        content: str,
        max_turns: int,
        sources: list[dict[str, Any]] | None,
        grounding_used: str | None = None,
        from_general_knowledge: bool = False,
        grounding_segments: list[dict[str, str]] | None = None,
    ) -> None:
        conn = self._connection()
        self._ensure_schema(conn)
        max_turn = conn.execute(_MAX_TURN, (tenant, conversation_id)).fetchall()[0][0]
        turn = 0 if max_turn is None else max_turn + 1
        now = datetime.now(UTC).isoformat()
        conn.execute(
            _INSERT_TURN,
            (
                tenant,
                conversation_id,
                turn,
                role,
                content,
                now,
                _dump_sources(sources),
                grounding_used,
                int(from_general_knowledge),
                _dump_grounding_segments(grounding_segments),
            ),
        )
        # Keep only the newest `max_turns` turn numbers: `cutoff` is the smallest one to KEEP.
        cutoff = turn - max_turns + 1
        if cutoff > 0:
            conn.execute(_DELETE_OLD_TURNS, (tenant, conversation_id, cutoff))
        conn.execute(_UPSERT_META, (tenant, conversation_id, now, now))
        conn.commit()

    def _history_job(self, tenant: str, conversation_id: str) -> list[ConversationTurn]:
        conn = self._connection()
        self._ensure_schema(conn)
        rows = conn.execute(_SELECT_HISTORY, (tenant, conversation_id)).fetchall()
        return [
            ConversationTurn(
                role=row[0],
                content=row[1],
                turn=row[2],
                created_at=row[3],
                sources=_load_sources(row[4]),
                grounding_used=row[5],
                from_general_knowledge=bool(row[6]) if row[6] is not None else False,
                grounding_segments=_load_grounding_segments(row[7]),
            )
            for row in rows
        ]

    def _prune_expired_job(self, tenant: str, ttl_days: int) -> int:
        conn = self._connection()
        self._ensure_schema(conn)
        cutoff = (datetime.now(UTC) - timedelta(days=ttl_days)).isoformat()
        stale_ids = [
            row[0]
            for row in conn.execute(_SELECT_STALE_CONVERSATION_IDS, (tenant, cutoff)).fetchall()
        ]
        if not stale_ids:
            return 0
        # Set-based prune: one COUNT + two DELETEs keyed on the whole stale set, instead of the
        # old per-conversation COUNT+DELETE+DELETE loop (1 + 3*M statements → 3 total).
        # The only interpolated text is `placeholders` — a run of bound `?` markers built purely
        # from len(stale_ids); every actual value is passed via `params`, so despite the f-strings
        # this is NOT SQL injection (bandit B608 is a false positive here, hence the nosec markers).
        placeholders = ",".join("?" * len(stale_ids))
        params = (tenant, *stale_ids)
        deleted = conn.execute(
            f"SELECT COUNT(*) FROM conversations "  # nosec B608
            f"WHERE tenant = ? AND conversation_id IN ({placeholders})",
            params,
        ).fetchall()[0][0]
        conn.execute(
            f"DELETE FROM conversations "  # nosec B608
            f"WHERE tenant = ? AND conversation_id IN ({placeholders})",
            params,
        )
        conn.execute(
            f"DELETE FROM conversations_meta "  # nosec B608
            f"WHERE tenant = ? AND conversation_id IN ({placeholders})",
            params,
        )
        conn.commit()
        return deleted

    def _set_title_if_unset_job(self, tenant: str, conversation_id: str, title: str) -> None:
        conn = self._connection()
        self._ensure_schema(conn)
        conn.execute(_UPDATE_TITLE_IF_UNSET, (title, tenant, conversation_id))
        conn.commit()

    def _list_conversations_job(
        self, tenant: str, limit: int, offset: int
    ) -> list[ConversationMeta]:
        conn = self._connection()
        self._ensure_schema(conn)
        rows = conn.execute(_SELECT_META_LIST, (tenant, limit, offset)).fetchall()
        return [
            ConversationMeta(
                conversation_id=row[0],
                title=row[1],
                created_at=row[2],
                updated_at=row[3],
                turn_count=row[4],
            )
            for row in rows
        ]

    def _get_conversation_job(self, tenant: str, conversation_id: str) -> ConversationDetail | None:
        conn = self._connection()
        self._ensure_schema(conn)
        meta_row = conn.execute(_SELECT_META, (tenant, conversation_id)).fetchall()
        turns = self._history_job(tenant, conversation_id)
        if not meta_row:
            if not turns:
                return None
            # Self-heal: a conversation with turns but no meta row predates T6 (D42) — the
            # meta table didn't exist when it was written. Backfill from the turns themselves
            # (title stays unset, exactly like any other un-titled conversation) so a GET
            # doesn't 404 on data that genuinely exists, and future `list_conversations` calls
            # pick it up too.
            created_at, updated_at = turns[0].created_at, turns[-1].created_at
            conn.execute(_UPSERT_META, (tenant, conversation_id, created_at, updated_at))
            conn.commit()
            title = None
        else:
            title, created_at, updated_at = meta_row[0]
        meta = ConversationMeta(
            conversation_id=conversation_id,
            title=title,
            created_at=created_at,
            updated_at=updated_at,
            turn_count=len(turns),
        )
        return ConversationDetail(meta=meta, turns=turns)

    def _delete_conversation_job(self, tenant: str, conversation_id: str) -> None:
        conn = self._connection()
        self._ensure_schema(conn)
        conn.execute(_DELETE_CONVERSATION, (tenant, conversation_id))
        conn.execute(_DELETE_CONVERSATION_META, (tenant, conversation_id))
        conn.commit()

    def _close_job(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
