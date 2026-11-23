"""libSQL/Turso-backed :class:`~sift.core.ports.VectorStore` adapter.

Async-over-sync: the ``libsql`` SDK is synchronous (sqlite3-style; writes need
``commit()``), so this store owns **one** connection that is only ever touched from a
**single-worker** :class:`~concurrent.futures.ThreadPoolExecutor`. The connection is
created lazily on that worker thread (avoiding ``check_same_thread`` violations), and every
async port method dispatches exactly one executor job that runs the whole operation —
including ``conn.commit()`` — to completion. An :class:`asyncio.Lock` serializes the write
methods to make the single-writer intent explicit.

Vector search uses libSQL's native ``F32_BLOB``/``vector32``/``vector_distance_cos``.
Cosine *distance* = 1 − similarity, so ``Hit.score = 1.0 - distance`` (≈ 1.0 for an
exact-text match), matching :class:`~sift.adapters.store.fake.FakeVectorStore`.

Keyword search uses SQLite's FTS5 (BM25 ranking) over ``chunks.text``: an external-content
index, so the text isn't stored twice, kept in sync by triggers on ``chunks``. Every write
path, including ones added later, updates it without remembering to. If the database can't
create FTS5 tables (a server built without the module), keyword search returns no hits and
retrieval falls back to vectors alone.
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import libsql

from sift.core.errors import ModelPinMismatch, SiftError
from sift.core.text import STOPWORDS, words
from sift.core.types import Chunk, DocumentInfo, Hit, SearchFilters, Vector

# ``libsql`` is a stub-less compiled extension; route attribute access through ``Any`` so
# the rest of this module stays fully type-checked.
_libsql: Any = libsql

logger = logging.getLogger(__name__)

_DDL_MODEL_PIN = (
    "CREATE TABLE IF NOT EXISTS model_pin (tenant TEXT PRIMARY KEY, model TEXT, dim INTEGER)"  # noqa: E501
)

_DDL_FILES = (
    "CREATE TABLE IF NOT EXISTS files ("
    "tenant TEXT, content_hash TEXT, path TEXT, indexed_at TEXT, modified_at TEXT, "
    "PRIMARY KEY (tenant, content_hash))"
)

# Additive migration for databases created before ``modified_at`` existed: SQLite has no
# "ADD COLUMN IF NOT EXISTS", so probe ``pragma_table_info`` and add it only when missing.
_FILES_HAS_MODIFIED_AT = "SELECT 1 FROM pragma_table_info('files') WHERE name = 'modified_at'"
_ALTER_FILES_ADD_MODIFIED_AT = "ALTER TABLE files ADD COLUMN modified_at TEXT"

_DDL_CHUNKS = (
    "CREATE TABLE IF NOT EXISTS chunks ("
    "tenant TEXT, source_hash TEXT, idx INTEGER, text TEXT, source_path TEXT, page INTEGER, "
    "embedding F32_BLOB({dim}) NOT NULL, metadata TEXT, "
    "PRIMARY KEY (tenant, source_hash, idx))"
)

# Additive migration for databases created before ``metadata`` existed on ``chunks`` — same
# ALTER-if-missing pattern as ``modified_at`` on ``files`` above.
_CHUNKS_HAS_METADATA = "SELECT 1 FROM pragma_table_info('chunks') WHERE name = 'metadata'"
_ALTER_CHUNKS_ADD_METADATA = "ALTER TABLE chunks ADD COLUMN metadata TEXT"

_INSERT_CHUNK = (
    "INSERT INTO chunks (tenant, source_hash, idx, text, source_path, page, embedding, metadata) "
    "VALUES (?, ?, ?, ?, ?, ?, vector32(?), ?) "
    "ON CONFLICT(tenant, source_hash, idx) DO UPDATE SET "
    "text = excluded.text, source_path = excluded.source_path, "
    "page = excluded.page, embedding = excluded.embedding, metadata = excluded.metadata"
)

_INSERT_FILE = (
    "INSERT INTO files (tenant, content_hash, path, indexed_at, modified_at) "
    "VALUES (?, ?, ?, ?, ?) "
    "ON CONFLICT(tenant, content_hash) DO UPDATE SET "
    "path = excluded.path, indexed_at = excluded.indexed_at, "
    "modified_at = excluded.modified_at"
)

# The keyword index. External content: FTS5 stores only the inverted index and reads the text
# back from ``chunks`` by rowid. ``chunks`` rowids stay put (the store never VACUUMs); if they
# ever moved, ``INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')`` re-derives the index.
_DDL_CHUNKS_FTS = (
    "CREATE VIRTUAL TABLE chunks_fts USING fts5("
    "text, content='chunks', content_rowid='rowid', tokenize='unicode61')"
)
_FTS_TRIGGERS = (
    "CREATE TRIGGER IF NOT EXISTS chunks_fts_insert AFTER INSERT ON chunks BEGIN "
    "INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text); END",
    "CREATE TRIGGER IF NOT EXISTS chunks_fts_delete AFTER DELETE ON chunks BEGIN "
    "INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text); END",
    "CREATE TRIGGER IF NOT EXISTS chunks_fts_update AFTER UPDATE OF text ON chunks BEGIN "
    "INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.rowid, old.text); "
    "INSERT INTO chunks_fts(rowid, text) VALUES (new.rowid, new.text); END",
)
_DROP_FTS = (
    "DROP TRIGGER IF EXISTS chunks_fts_insert",
    "DROP TRIGGER IF EXISTS chunks_fts_delete",
    "DROP TRIGGER IF EXISTS chunks_fts_update",
    "DROP TABLE IF EXISTS chunks_fts",
)
# Indexes every chunk already in the table: run once, when an older database gets the index.
_REBUILD_CHUNKS_FTS = "INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')"
_FTS_TABLE_EXISTS = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'chunks_fts'"

# A pasted paragraph shouldn't become a 300-term query; the first distinct words carry it.
_FTS_MAX_TERMS = 64

_PIN_TABLE_EXISTS = "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'model_pin'"

_FILES_TABLE_EXISTS = "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'files'"

_SELECT_PIN = "SELECT model, dim FROM model_pin WHERE tenant = ?"

_INSERT_PIN = "INSERT INTO model_pin (tenant, model, dim) VALUES (?, ?, ?)"

_SEARCH_BASE = (
    "SELECT c.text, c.source_path, c.page, c.source_hash, c.idx, "
    "vector_distance_cos(c.embedding, vector32(?)) AS d, f.indexed_at, f.modified_at, c.metadata "
    "FROM chunks c "
    "LEFT JOIN files f ON f.tenant = c.tenant AND f.content_hash = c.source_hash "
    "WHERE {where} ORDER BY d ASC LIMIT ?"
)

_KEYWORD_SEARCH_BASE = (
    "SELECT c.text, c.source_path, c.page, c.source_hash, c.idx, "
    "vector_distance_cos(c.embedding, vector32(?)) AS d, f.indexed_at, f.modified_at, c.metadata "
    "FROM chunks_fts "
    "JOIN chunks c ON c.rowid = chunks_fts.rowid "
    "LEFT JOIN files f ON f.tenant = c.tenant AND f.content_hash = c.source_hash "
    "WHERE chunks_fts MATCH ? AND {where} ORDER BY bm25(chunks_fts), c.rowid LIMIT ?"
)

_SELECT_HASHES = "SELECT content_hash FROM files WHERE tenant = ?"

_SELECT_DOCUMENTS_BASE = (
    "SELECT f.path, f.content_hash, COUNT(c.idx), f.modified_at, f.indexed_at "
    "FROM files f "
    "LEFT JOIN chunks c ON c.tenant = f.tenant AND c.source_hash = f.content_hash "
    "WHERE {where} "
    "GROUP BY f.content_hash, f.path, f.indexed_at, f.modified_at "
    "ORDER BY f.indexed_at DESC"
)

# Total documents (one row per file) under the same filter — for a paged listing's `total`.
_COUNT_DOCUMENTS_BASE = "SELECT COUNT(*) FROM files f WHERE {where}"

_SELECT_CHUNKS_BY_HASH = (
    "SELECT c.text, c.source_path, c.page, c.source_hash, c.idx, c.metadata, f.modified_at "
    "FROM chunks c "
    "LEFT JOIN files f ON f.tenant = c.tenant AND f.content_hash = c.source_hash "
    "WHERE c.tenant = ? AND c.source_hash = ? ORDER BY c.idx ASC"
)

_COUNT_CHUNKS_BY_HASH = "SELECT COUNT(*) FROM chunks WHERE tenant = ? AND source_hash = ?"

_DELETE_CHUNKS_BY_HASH = "DELETE FROM chunks WHERE tenant = ? AND source_hash = ?"

_DELETE_FILE_BY_HASH = "DELETE FROM files WHERE tenant = ? AND content_hash = ?"


def _vector_json(vector: Vector) -> str:
    """Serialize a vector to the JSON array literal ``vector32`` accepts."""
    return json.dumps([float(component) for component in vector])


def _fts_query(text: str) -> str | None:
    """Turn free text into an FTS5 query: its distinct words, each quoted, OR-ed together.

    Quoting makes every word a literal (no FTS5 operators or column filters from user input);
    a word the tokenizer splits, like ``T1566.001``, becomes a phrase that matches its parts in
    order. Stopwords are dropped unless nothing else is left. ``None`` when ``text`` has no
    words at all.
    """
    # Stopwords are too common to help a match: BM25 already gives them little weight, but each
    # one still pulls in matches, and dropping them measurably sharpens the ranking.
    distinct = list(dict.fromkeys(words(text)))
    kept = [word for word in distinct if word not in STOPWORDS] or distinct
    if not kept:
        return None
    return " OR ".join(f'"{word}"' for word in kept[:_FTS_MAX_TERMS])


def _filter_clauses(tenant: str, filters: SearchFilters | None) -> tuple[list[str], list[Any]]:
    """The tenant + ``filters`` WHERE clauses shared by vector and keyword search: metadata
    equality via ``json_extract``, ``modified_at`` range via a plain string comparison
    (consistent zero-padded ISO-8601 sorts lexicographically the same as chronologically — no
    datetime parsing needed store-side)."""
    clauses = ["c.tenant = ?"]
    params: list[Any] = [tenant]
    if filters is not None:
        if filters.metadata:
            for key, value in filters.metadata.items():
                clauses.append("json_extract(c.metadata, ?) = ?")
                params.append(f"$.{key}")
                params.append(value)
        if filters.since is not None:
            clauses.append("f.modified_at >= ?")
            params.append(filters.since)
        if filters.until is not None:
            clauses.append("f.modified_at <= ?")
            params.append(filters.until)
    return clauses, params


def _search_sql(
    tenant: str, vector: Vector, k: int, filters: SearchFilters | None
) -> tuple[str, list[Any]]:
    """Build the ``search`` SQL + its bound params, narrowing by ``filters`` BEFORE the
    ``LIMIT``."""
    clauses, params = _filter_clauses(tenant, filters)
    sql = _SEARCH_BASE.format(where=" AND ".join(clauses))
    return sql, [_vector_json(vector), *params, k]


def _keyword_search_sql(
    match: str, tenant: str, vector: Vector, k: int, filters: SearchFilters | None
) -> tuple[str, list[Any]]:
    """Build the ``keyword_search`` SQL: BM25 order over the FTS5 match, the same tenant and
    ``filters`` narrowing as :func:`_search_sql`, and each hit's cosine distance to ``vector``
    so its score means what a vector hit's score means."""
    clauses, params = _filter_clauses(tenant, filters)
    sql = _KEYWORD_SEARCH_BASE.format(where=" AND ".join(clauses))
    return sql, [_vector_json(vector), match, *params, k]


def _hit(row: Sequence[Any]) -> Hit:
    """A :class:`Hit` from a ``_SEARCH_BASE``/``_KEYWORD_SEARCH_BASE`` row."""
    return Hit(
        text=row[0],
        score=1.0 - row[5],
        source_path=row[1],
        page=row[2],
        source_hash=row[3],
        index=row[4],
        indexed_at=row[6],
        modified_at=row[7],
        metadata=json.loads(row[8]) if row[8] else None,
    )


def _documents_where(metadata: Mapping[str, str] | None) -> tuple[str, list[Any]]:
    """The shared WHERE clause + bound params for ``list_documents``/``count_documents``: a
    document matches ``metadata`` when at least one of its chunks carries every given key/value
    (equality, via ``json_extract``)."""
    clauses = ["f.tenant = ?"]
    params: list[Any] = []
    if metadata:
        for key, value in metadata.items():
            clauses.append(
                "EXISTS (SELECT 1 FROM chunks mc WHERE mc.tenant = f.tenant AND "
                "mc.source_hash = f.content_hash AND json_extract(mc.metadata, ?) = ?)"
            )
            params.append(f"$.{key}")
            params.append(value)
    return " AND ".join(clauses), params


def _documents_sql(
    metadata: Mapping[str, str] | None, limit: int | None, offset: int
) -> tuple[str, list[Any]]:
    """Build the ``list_documents`` SQL + its bound params, paging in the DB when ``limit`` is
    set (``LIMIT ? OFFSET ?``) so only the requested page is materialized, not every row."""
    where, params = _documents_where(metadata)
    sql = _SELECT_DOCUMENTS_BASE.format(where=where)
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)
    return sql, params


def _count_documents_sql(metadata: Mapping[str, str] | None) -> tuple[str, list[Any]]:
    """Build the ``count_documents`` SQL: COUNT over the grouped document set (one row per file)
    under the same ``tenant``/``metadata`` filter as :func:`_documents_sql`."""
    where, params = _documents_where(metadata)
    sql = _COUNT_DOCUMENTS_BASE.format(where=where)
    return sql, params


class LibSQLStore:
    """``VectorStore`` over a local-file or Turso libSQL database."""

    def __init__(self, database: str, *, auth_token: str | None = None) -> None:
        self._database = database
        self._auth_token = auth_token
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = asyncio.Lock()
        self._conn: Any = None
        # Whether ``chunks_fts`` exists: set by ``ensure_ready``, or looked up on first use.
        self._has_fts: bool | None = None

    # --- async-over-sync plumbing -------------------------------------------------

    def _connection(self) -> Any:
        """Return the worker-thread-owned connection, creating it lazily.

        Only ever called from within an executor job, so the connection is born on, and
        forever bound to, the single worker thread.
        """
        if self._conn is None:
            if self._auth_token is not None:
                self._conn = _libsql.connect(self._database, auth_token=self._auth_token)
            else:
                self._conn = _libsql.connect(self._database)
        return self._conn

    async def _submit[T](self, job: Callable[[], T]) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, job)

    # --- VectorStore port ---------------------------------------------------------

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None:
        async with self._lock:
            await self._submit(functools.partial(self._ensure_ready_job, model, dim, tenant))

    async def upsert(self, chunks: Sequence[Chunk], tenant: str) -> None:
        async with self._lock:
            await self._submit(functools.partial(self._upsert_job, tuple(chunks), tenant))

    async def search(
        self, vector: Vector, k: int, tenant: str, filters: SearchFilters | None = None
    ) -> list[Hit]:
        return await self._submit(functools.partial(self._search_job, vector, k, tenant, filters))

    async def known_hashes(self, tenant: str) -> set[str]:
        return await self._submit(functools.partial(self._known_hashes_job, tenant))

    # --- keyword-search seam (SupportsKeywordSearch) ------------------------------

    async def keyword_search(
        self,
        query: str,
        vector: Vector,
        k: int,
        tenant: str,
        filters: SearchFilters | None = None,
    ) -> list[Hit]:
        # Read-only: no lock, mirroring search.
        return await self._submit(
            functools.partial(self._keyword_search_job, query, vector, k, tenant, filters)
        )

    # --- document-admin seam (SupportsDocumentAdmin) ------------------------------

    async def list_documents(
        self,
        tenant: str,
        metadata: Mapping[str, str] | None = None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DocumentInfo]:
        # Read-only: no lock, mirroring search / known_hashes.
        return await self._submit(
            functools.partial(self._list_documents_job, tenant, metadata, limit, offset)
        )

    async def count_documents(self, tenant: str, metadata: Mapping[str, str] | None = None) -> int:
        # Read-only: no lock, mirroring list_documents.
        return await self._submit(functools.partial(self._count_documents_job, tenant, metadata))

    async def delete_document(self, source_hash: str, tenant: str) -> int:
        async with self._lock:
            return await self._submit(
                functools.partial(self._delete_document_job, source_hash, tenant)
            )

    # --- chunk-access seam (SupportsChunkAccess) ----------------------------------

    async def get_chunks(self, source_hash: str, tenant: str) -> list[Chunk]:
        # Read-only: no lock, mirroring search / list_documents.
        return await self._submit(functools.partial(self._get_chunks_job, source_hash, tenant))

    async def aclose(self) -> None:
        await self._submit(self._close_job)
        self._executor.shutdown(wait=True)

    # --- executor jobs (run on the single worker thread) --------------------------

    def _ensure_ready_job(self, model: str, dim: int, tenant: str) -> None:
        conn = self._connection()
        conn.execute(_DDL_MODEL_PIN)
        conn.execute(_DDL_FILES)
        conn.execute(_DDL_CHUNKS.format(dim=dim))
        if not conn.execute(_FILES_HAS_MODIFIED_AT).fetchall():
            conn.execute(_ALTER_FILES_ADD_MODIFIED_AT)  # migrate a pre-``modified_at`` database
        if not conn.execute(_CHUNKS_HAS_METADATA).fetchall():
            conn.execute(_ALTER_CHUNKS_ADD_METADATA)  # migrate a pre-``metadata`` database
        conn.commit()
        if self._has_fts is None:  # ensure_ready runs on every search; check the index once
            self._ensure_fts(conn)

        rows = conn.execute(_SELECT_PIN, (tenant,)).fetchall()
        if not rows:
            conn.execute(_INSERT_PIN, (tenant, model, dim))
            conn.commit()
            return
        pinned = (rows[0][0], rows[0][1])
        if pinned != (model, dim):
            raise ModelPinMismatch(tenant=tenant, expected=pinned, actual=(model, dim))

    def _upsert_job(self, chunks: Sequence[Chunk], tenant: str) -> None:
        conn = self._connection()
        if not conn.execute(_PIN_TABLE_EXISTS).fetchall():
            raise SiftError(f"tenant {tenant!r} not initialized; call ensure_ready() first")
        rows = conn.execute(_SELECT_PIN, (tenant,)).fetchall()
        if not rows:
            raise SiftError(f"tenant {tenant!r} not initialized; call ensure_ready() first")
        dim = rows[0][1]

        now = datetime.now(UTC).isoformat()
        # The `files` row is per-source-hash, but every chunk of one document carries the same
        # source_hash/source_path/modified_at — so upserting it inside the chunk loop wrote the
        # same row N times (N-1 redundant round-trips against remote Turso). Collect one file row
        # per unique source_hash (last chunk wins, matching the old per-chunk ON CONFLICT order)
        # and upsert each once after the chunks.
        file_rows: dict[str, tuple[str, str | None]] = {}
        for chunk in chunks:
            if chunk.vector is None:
                raise ValueError(f"chunk {chunk.source_hash}:{chunk.index} has no vector")
            if len(chunk.vector) != dim:
                raise ValueError(
                    f"vector dim {len(chunk.vector)} != pinned dim {dim} "
                    f"for chunk {chunk.source_hash}:{chunk.index}"
                )
            conn.execute(
                _INSERT_CHUNK,
                (
                    tenant,
                    chunk.source_hash,
                    chunk.index,
                    chunk.text,
                    chunk.source_path,
                    chunk.page,
                    _vector_json(chunk.vector),
                    json.dumps(chunk.metadata) if chunk.metadata is not None else None,
                ),
            )
            file_rows[chunk.source_hash] = (chunk.source_path, chunk.modified_at)
        for source_hash, (source_path, modified_at) in file_rows.items():
            conn.execute(_INSERT_FILE, (tenant, source_hash, source_path, now, modified_at))
        conn.commit()

    def _ensure_fts(self, conn: Any) -> None:
        """Create the keyword index and its triggers if missing, indexing existing chunks.

        A database from before keyword search gets the index on its first ``ensure_ready``;
        the one-time rebuild reads every chunk, so it costs about as long as one full scan.
        Any failure (a server without FTS5, say) leaves search on vectors alone rather than
        failing it.
        """
        try:
            if not conn.execute(_FTS_TABLE_EXISTS).fetchall():
                conn.execute(_DDL_CHUNKS_FTS)
                logger.info("creating the keyword index; chunks already stored are indexed once")
                conn.execute(_REBUILD_CHUNKS_FTS)
            for trigger in _FTS_TRIGGERS:
                conn.execute(trigger)
            conn.commit()
        except ValueError as error:  # libsql reports SQLite errors as ValueError
            logger.warning("keyword index unavailable (%s); search uses vectors only", error)
            self._drop_fts(conn)
            self._has_fts = False
            return
        self._has_fts = True

    def _drop_fts(self, conn: Any) -> None:
        """Remove a half-made keyword index. DDL commits as it runs, so a failure part-way can
        leave the table without its triggers, and an index nothing updates goes stale. The
        next start builds it again from scratch."""
        try:
            conn.rollback()
            for statement in _DROP_FTS:
                conn.execute(statement)
            conn.commit()
        except ValueError as error:
            logger.warning("could not remove the partial keyword index (%s)", error)

    def _search_job(
        self, vector: Vector, k: int, tenant: str, filters: SearchFilters | None
    ) -> list[Hit]:
        conn = self._connection()
        sql, params = _search_sql(tenant, vector, k, filters)
        return [_hit(row) for row in conn.execute(sql, params).fetchall()]

    def _keyword_search_job(
        self, query: str, vector: Vector, k: int, tenant: str, filters: SearchFilters | None
    ) -> list[Hit]:
        conn = self._connection()
        if self._has_fts is None:
            self._has_fts = bool(conn.execute(_FTS_TABLE_EXISTS).fetchall())
        match = _fts_query(query)
        if not self._has_fts or match is None:
            return []
        sql, params = _keyword_search_sql(match, tenant, vector, k, filters)
        return [_hit(row) for row in conn.execute(sql, params).fetchall()]

    def _known_hashes_job(self, tenant: str) -> set[str]:
        conn = self._connection()
        # A fresh database has no schema until the first ingest runs ``ensure_ready``. The
        # agent dedups by reading the manifest *before* it ever uploads, so guard the read
        # and report an empty store rather than crashing on ``no such table: files``.
        if not conn.execute(_FILES_TABLE_EXISTS).fetchall():
            return set()
        rows = conn.execute(_SELECT_HASHES, (tenant,)).fetchall()
        return {row[0] for row in rows}

    def _list_documents_job(
        self, tenant: str, metadata: Mapping[str, str] | None, limit: int | None, offset: int
    ) -> list[DocumentInfo]:
        conn = self._connection()
        # Same fresh-database guard as ``_known_hashes_job``: the document list is read
        # before the first ingest creates the schema, so an empty store is "no documents".
        if not conn.execute(_FILES_TABLE_EXISTS).fetchall():
            return []
        sql, extra_params = _documents_sql(metadata, limit, offset)
        rows = conn.execute(sql, (tenant, *extra_params)).fetchall()
        return [
            DocumentInfo(
                source_path=row[0],
                source_hash=row[1],
                chunks=row[2],
                modified_at=row[3],
                indexed_at=row[4],
            )
            for row in rows
        ]

    def _count_documents_job(self, tenant: str, metadata: Mapping[str, str] | None) -> int:
        conn = self._connection()
        # Same fresh-database guard as ``_list_documents_job``: no schema yet ⇒ zero documents.
        if not conn.execute(_FILES_TABLE_EXISTS).fetchall():
            return 0
        sql, extra_params = _count_documents_sql(metadata)
        return conn.execute(sql, (tenant, *extra_params)).fetchall()[0][0]

    def _get_chunks_job(self, source_hash: str, tenant: str) -> list[Chunk]:
        conn = self._connection()
        # Same fresh-database guard as ``_known_hashes_job``/``_list_documents_job``: reading
        # before any ``ensure_ready()`` call must report "no chunks", never a table-missing crash.
        if not conn.execute(_FILES_TABLE_EXISTS).fetchall():
            return []
        rows = conn.execute(_SELECT_CHUNKS_BY_HASH, (tenant, source_hash)).fetchall()
        return [
            Chunk(
                text=row[0],
                source_path=row[1],
                page=row[2],
                source_hash=row[3],
                index=row[4],
                metadata=json.loads(row[5]) if row[5] else None,
                modified_at=row[6],
            )
            for row in rows
        ]

    def _delete_document_job(self, source_hash: str, tenant: str) -> int:
        conn = self._connection()
        count = conn.execute(_COUNT_CHUNKS_BY_HASH, (tenant, source_hash)).fetchall()[0][0]
        conn.execute(_DELETE_CHUNKS_BY_HASH, (tenant, source_hash))
        conn.execute(_DELETE_FILE_BY_HASH, (tenant, source_hash))
        conn.commit()
        return count

    def _close_job(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
