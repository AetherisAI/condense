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
"""

from __future__ import annotations

import asyncio
import functools
import json
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import libsql

from sift.core.errors import ModelPinMismatch, SiftError
from sift.core.types import Chunk, DocumentInfo, Hit, SearchFilters, Vector

# ``libsql`` is a stub-less compiled extension; route attribute access through ``Any`` so
# the rest of this module stays fully type-checked.
_libsql: Any = libsql

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
# ALTER-if-missing pattern as ``modified_at`` on ``files`` above (D28).
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

_SELECT_HASHES = "SELECT content_hash FROM files WHERE tenant = ?"

_SELECT_DOCUMENTS_BASE = (
    "SELECT f.path, f.content_hash, COUNT(c.idx), f.modified_at, f.indexed_at "
    "FROM files f "
    "LEFT JOIN chunks c ON c.tenant = f.tenant AND c.source_hash = f.content_hash "
    "WHERE {where} "
    "GROUP BY f.content_hash, f.path, f.indexed_at, f.modified_at "
    "ORDER BY f.indexed_at DESC"
)

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


def _search_sql(
    tenant: str, vector: Vector, k: int, filters: SearchFilters | None
) -> tuple[str, list[Any]]:
    """Build the ``search`` SQL + its bound params, narrowing by ``filters`` BEFORE the ``LIMIT``
    (WP v0.2.0 T2, D38): metadata equality via ``json_extract``, ``modified_at`` range via a
    plain string comparison (consistent zero-padded ISO-8601 sorts lexicographically the same as
    chronologically — no datetime parsing needed store-side)."""
    clauses = ["c.tenant = ?"]
    params: list[Any] = [_vector_json(vector), tenant]
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
    sql = _SEARCH_BASE.format(where=" AND ".join(clauses))
    params.append(k)
    return sql, params


def _documents_sql(metadata: Mapping[str, str] | None) -> tuple[str, list[Any]]:
    """Build the ``list_documents`` SQL + its bound params: a document matches ``metadata`` when
    at least one of its chunks carries every given key/value (equality, via ``json_extract``)."""
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
    sql = _SELECT_DOCUMENTS_BASE.format(where=" AND ".join(clauses))
    return sql, params


class LibSQLStore:
    """``VectorStore`` over a local-file or Turso libSQL database."""

    def __init__(self, database: str, *, auth_token: str | None = None) -> None:
        self._database = database
        self._auth_token = auth_token
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = asyncio.Lock()
        self._conn: Any = None

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

    # --- document-admin seam (SupportsDocumentAdmin) ------------------------------

    async def list_documents(
        self, tenant: str, metadata: Mapping[str, str] | None = None
    ) -> list[DocumentInfo]:
        # Read-only: no lock, mirroring search / known_hashes.
        return await self._submit(functools.partial(self._list_documents_job, tenant, metadata))

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
            conn.execute(
                _INSERT_FILE,
                (tenant, chunk.source_hash, chunk.source_path, now, chunk.modified_at),
            )
        conn.commit()

    def _search_job(
        self, vector: Vector, k: int, tenant: str, filters: SearchFilters | None
    ) -> list[Hit]:
        conn = self._connection()
        sql, params = _search_sql(tenant, vector, k, filters)
        rows = conn.execute(sql, params).fetchall()
        return [
            Hit(
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
            for row in rows
        ]

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
        self, tenant: str, metadata: Mapping[str, str] | None
    ) -> list[DocumentInfo]:
        conn = self._connection()
        # Same fresh-database guard as ``_known_hashes_job``: the document list is read
        # before the first ingest creates the schema, so an empty store is "no documents".
        if not conn.execute(_FILES_TABLE_EXISTS).fetchall():
            return []
        sql, extra_params = _documents_sql(metadata)
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
