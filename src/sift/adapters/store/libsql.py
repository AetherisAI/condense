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
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import libsql

from sift.core.errors import ModelPinMismatch, SiftError
from sift.core.types import Chunk, DocumentInfo, Hit, Vector

# ``libsql`` is a stub-less compiled extension; route attribute access through ``Any`` so
# the rest of this module stays fully type-checked.
_libsql: Any = libsql

_DDL_MODEL_PIN = (
    "CREATE TABLE IF NOT EXISTS model_pin (tenant TEXT PRIMARY KEY, model TEXT, dim INTEGER)"  # noqa: E501
)

_DDL_FILES = (
    "CREATE TABLE IF NOT EXISTS files ("
    "tenant TEXT, content_hash TEXT, path TEXT, indexed_at TEXT, "
    "PRIMARY KEY (tenant, content_hash))"
)

_DDL_CHUNKS = (
    "CREATE TABLE IF NOT EXISTS chunks ("
    "tenant TEXT, source_hash TEXT, idx INTEGER, text TEXT, source_path TEXT, page INTEGER, "
    "embedding F32_BLOB({dim}) NOT NULL, "
    "PRIMARY KEY (tenant, source_hash, idx))"
)

_INSERT_CHUNK = (
    "INSERT INTO chunks (tenant, source_hash, idx, text, source_path, page, embedding) "
    "VALUES (?, ?, ?, ?, ?, ?, vector32(?)) "
    "ON CONFLICT(tenant, source_hash, idx) DO UPDATE SET "
    "text = excluded.text, source_path = excluded.source_path, "
    "page = excluded.page, embedding = excluded.embedding"
)

_INSERT_FILE = (
    "INSERT INTO files (tenant, content_hash, path, indexed_at) VALUES (?, ?, ?, ?) "
    "ON CONFLICT(tenant, content_hash) DO UPDATE SET "
    "path = excluded.path, indexed_at = excluded.indexed_at"
)

_PIN_TABLE_EXISTS = "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'model_pin'"

_SELECT_PIN = "SELECT model, dim FROM model_pin WHERE tenant = ?"

_INSERT_PIN = "INSERT INTO model_pin (tenant, model, dim) VALUES (?, ?, ?)"

_SEARCH = (
    "SELECT text, source_path, page, source_hash, idx, "
    "vector_distance_cos(embedding, vector32(?)) AS d "
    "FROM chunks WHERE tenant = ? ORDER BY d ASC LIMIT ?"
)

_SELECT_HASHES = "SELECT content_hash FROM files WHERE tenant = ?"

_SELECT_DOCUMENTS = (
    "SELECT f.path, f.content_hash, COUNT(c.idx) "
    "FROM files f "
    "LEFT JOIN chunks c ON c.tenant = f.tenant AND c.source_hash = f.content_hash "
    "WHERE f.tenant = ? "
    "GROUP BY f.content_hash, f.path, f.indexed_at "
    "ORDER BY f.indexed_at DESC"
)

_COUNT_CHUNKS_BY_HASH = "SELECT COUNT(*) FROM chunks WHERE tenant = ? AND source_hash = ?"

_DELETE_CHUNKS_BY_HASH = "DELETE FROM chunks WHERE tenant = ? AND source_hash = ?"

_DELETE_FILE_BY_HASH = "DELETE FROM files WHERE tenant = ? AND content_hash = ?"


def _vector_json(vector: Vector) -> str:
    """Serialize a vector to the JSON array literal ``vector32`` accepts."""
    return json.dumps([float(component) for component in vector])


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

    async def search(self, vector: Vector, k: int, tenant: str) -> list[Hit]:
        return await self._submit(functools.partial(self._search_job, vector, k, tenant))

    async def known_hashes(self, tenant: str) -> set[str]:
        return await self._submit(functools.partial(self._known_hashes_job, tenant))

    # --- document-admin seam (SupportsDocumentAdmin) ------------------------------

    async def list_documents(self, tenant: str) -> list[DocumentInfo]:
        # Read-only: no lock, mirroring search / known_hashes.
        return await self._submit(functools.partial(self._list_documents_job, tenant))

    async def delete_document(self, source_hash: str, tenant: str) -> int:
        async with self._lock:
            return await self._submit(
                functools.partial(self._delete_document_job, source_hash, tenant)
            )

    async def aclose(self) -> None:
        await self._submit(self._close_job)
        self._executor.shutdown(wait=True)

    # --- executor jobs (run on the single worker thread) --------------------------

    def _ensure_ready_job(self, model: str, dim: int, tenant: str) -> None:
        conn = self._connection()
        conn.execute(_DDL_MODEL_PIN)
        conn.execute(_DDL_FILES)
        conn.execute(_DDL_CHUNKS.format(dim=dim))
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
                ),
            )
            conn.execute(_INSERT_FILE, (tenant, chunk.source_hash, chunk.source_path, now))
        conn.commit()

    def _search_job(self, vector: Vector, k: int, tenant: str) -> list[Hit]:
        conn = self._connection()
        rows = conn.execute(_SEARCH, (_vector_json(vector), tenant, k)).fetchall()
        return [
            Hit(
                text=row[0],
                score=1.0 - row[5],
                source_path=row[1],
                page=row[2],
                source_hash=row[3],
                index=row[4],
            )
            for row in rows
        ]

    def _known_hashes_job(self, tenant: str) -> set[str]:
        conn = self._connection()
        rows = conn.execute(_SELECT_HASHES, (tenant,)).fetchall()
        return {row[0] for row in rows}

    def _list_documents_job(self, tenant: str) -> list[DocumentInfo]:
        conn = self._connection()
        rows = conn.execute(_SELECT_DOCUMENTS, (tenant,)).fetchall()
        return [DocumentInfo(source_path=row[0], source_hash=row[1], chunks=row[2]) for row in rows]

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
