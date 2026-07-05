"""Unit tests for :mod:`sift.pipelines.tools` — the ToolRegistry (WP v0.2.0 T2, D38).

Drives ``build_tool_registry`` through ``FakeEmbedder``/``FakeVectorStore`` (offline, no
network) — the same fakes every other pipeline test uses. Covers both renders
(``to_openai_functions``/``to_json_schema_manifest``) and each tool's executor end-to-end:
``search`` (incl. ``k`` default/cap and metadata/since/until filters), ``list_documents``
(pagination + total + metadata filter), and ``get_document_chunks`` (ordering).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings
from sift.core.ports import VectorStore
from sift.core.types import Chunk, Hit, Vector
from sift.pipelines.tools import ToolRegistry, build_tool_registry

MODEL = "bge-m3"
DIM = 16
TENANT = "default"


@pytest.fixture
def settings() -> Settings:
    return Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder(dim=DIM)


@pytest.fixture
def store() -> FakeVectorStore:
    return FakeVectorStore()


@pytest.fixture
def registry(embedder: FakeEmbedder, store: FakeVectorStore, settings: Settings) -> ToolRegistry:
    return build_tool_registry(embedder, store, settings)


async def _seed(store: VectorStore, embedder: FakeEmbedder, chunks: list[Chunk]) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    embedded = []
    for chunk in chunks:
        (vector,) = await embedder.embed([chunk.text])
        embedded.append(replace(chunk, vector=vector))
    await store.upsert(embedded, TENANT)


# --- registry shape ------------------------------------------------------------------


def test_tools_registers_search_list_documents_get_document_chunks(
    registry: ToolRegistry,
) -> None:
    names = {tool.name for tool in registry.tools()}
    assert names == {"search", "list_documents", "get_document_chunks"}


def test_to_openai_functions_shape(registry: ToolRegistry) -> None:
    functions = registry.to_openai_functions()

    assert len(functions) == 3
    for entry in functions:
        assert entry["type"] == "function"
        fn = entry["function"]
        assert isinstance(fn["name"], str)
        assert isinstance(fn["description"], str)
        assert fn["parameters"]["type"] == "object"
    names = {entry["function"]["name"] for entry in functions}
    assert names == {"search", "list_documents", "get_document_chunks"}


def test_to_json_schema_manifest_shape(registry: ToolRegistry) -> None:
    manifest = registry.to_json_schema_manifest()

    assert "tools" in manifest
    tools = manifest["tools"]
    assert len(tools) == 3
    for entry in tools:
        assert isinstance(entry["name"], str)
        assert isinstance(entry["description"], str)
        assert entry["parameters"]["type"] == "object"


async def test_call_unknown_tool_raises_key_error(registry: ToolRegistry) -> None:
    with pytest.raises(KeyError):
        await registry.call("nope", {}, TENANT)


# --- tool descriptions steer strategy (last open E2E item: enumeration budget blow-outs) ------
#
# Descriptions steer models — an enumeration question ("what documents/people exist") must be
# answered from `list_documents` alone; `get_document_chunks` must never look like the right
# tool for iterating a whole corpus. See `tests/pipelines/test_answer.py`'s matching system
# prompt assertion.


def test_list_documents_description_says_authoritative_for_enumeration(
    registry: ToolRegistry,
) -> None:
    spec = registry.get("list_documents")
    assert spec is not None
    description = spec.description.lower()
    assert "authoritative" in description
    assert "alone" in description


def test_get_document_chunks_description_warns_against_whole_corpus_iteration(
    registry: ToolRegistry,
) -> None:
    spec = registry.get("get_document_chunks")
    assert spec is not None
    description = spec.description.lower()
    assert "small" in description
    assert "never" in description or "not for" in description
    assert "corpus" in description


# --- D44: tool descriptions must steer time/recency questions to modified_at, never a filename -


def test_search_description_says_modified_at_and_metadata_over_filename_dates(
    registry: ToolRegistry,
) -> None:
    spec = registry.get("search")
    assert spec is not None
    description = spec.description.lower()
    assert "modified_at" in description
    assert "metadata" in description
    assert "filename" in description


def test_list_documents_description_says_modified_at_over_filename_dates(
    registry: ToolRegistry,
) -> None:
    spec = registry.get("list_documents")
    assert spec is not None
    description = spec.description.lower()
    assert "modified_at" in description
    assert "filename" in description


def test_get_document_chunks_description_says_modified_at_and_metadata(
    registry: ToolRegistry,
) -> None:
    spec = registry.get("get_document_chunks")
    assert spec is not None
    description = spec.description.lower()
    assert "modified_at" in description
    assert "metadata" in description


# --- search executor -------------------------------------------------------------------


async def test_search_executor_returns_ranked_hits_no_recap(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    await _seed(
        store,
        embedder,
        [
            Chunk(text="the sky is blue", source_path="a.md", page=1, source_hash="h1", index=0),
            Chunk(text="grass is green", source_path="b.md", page=2, source_hash="h2", index=0),
        ],
    )

    hits: list[Hit] = await registry.call("search", {"query": "the sky is blue"}, TENANT)

    assert hits
    assert hits[0].source_path == "a.md"
    assert hits[0].text == "the sky is blue"  # raw hit, no recap/summary anywhere


async def test_search_executor_defaults_k_from_settings(
    embedder: FakeEmbedder, store: FakeVectorStore
) -> None:
    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL, tools_search_k=2)
    registry = build_tool_registry(embedder, store, settings)
    await _seed(
        store,
        embedder,
        [
            Chunk(text=f"doc {i}", source_path=f"{i}.md", page=1, source_hash=f"h{i}", index=0)
            for i in range(5)
        ],
    )

    hits = await registry.call("search", {"query": "doc"}, TENANT)

    assert len(hits) == 2  # Settings.tools_search_k, not the store's whole corpus


async def test_search_executor_caps_k_at_max(
    embedder: FakeEmbedder, store: FakeVectorStore
) -> None:
    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL, tools_search_max_k=3)
    registry = build_tool_registry(embedder, store, settings)
    await _seed(
        store,
        embedder,
        [
            Chunk(text=f"doc {i}", source_path=f"{i}.md", page=1, source_hash=f"h{i}", index=0)
            for i in range(5)
        ],
    )

    hits = await registry.call("search", {"query": "doc", "k": 999}, TENANT)

    assert len(hits) == 3  # clamped to tools_search_max_k, not the requested 999


async def test_search_executor_metadata_filter(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    await _seed(
        store,
        embedder,
        [
            Chunk(
                text="alpha one",
                source_path="a.md",
                page=1,
                source_hash="h1",
                index=0,
                metadata={"project": "condense"},
            ),
            Chunk(text="alpha two", source_path="b.md", page=1, source_hash="h2", index=0),
        ],
    )

    hits = await registry.call(
        "search", {"query": "alpha", "filters": {"metadata": {"project": "condense"}}}, TENANT
    )

    assert [hit.source_path for hit in hits] == ["a.md"]


async def test_search_executor_hit_includes_modified_at_and_metadata(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    """D44: a `search` hit must carry the source file's `modified_at` plus its `metadata` — the
    temporal + tagging signals a tool consumer needs (never guessed from a filename)."""
    await _seed(
        store,
        embedder,
        [
            Chunk(
                text="gamma one",
                source_path="g.md",
                page=1,
                source_hash="hg",
                index=0,
                modified_at="2026-03-04T05:06:07+00:00",
                metadata={"project": "condense"},
            ),
        ],
    )

    (hit,) = await registry.call("search", {"query": "gamma one"}, TENANT)

    assert hit.modified_at == "2026-03-04T05:06:07+00:00"
    assert hit.metadata == {"project": "condense"}


async def test_search_executor_since_until_filter(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    await _seed(
        store,
        embedder,
        [
            Chunk(
                text="beta old",
                source_path="old.md",
                page=1,
                source_hash="ho",
                index=0,
                modified_at="2026-01-01T00:00:00+00:00",
            ),
            Chunk(
                text="beta new",
                source_path="new.md",
                page=1,
                source_hash="hn",
                index=0,
                modified_at="2026-06-01T00:00:00+00:00",
            ),
        ],
    )

    hits = await registry.call(
        "search", {"query": "beta", "filters": {"since": "2026-03-01"}}, TENANT
    )

    assert [hit.source_path for hit in hits] == ["new.md"]


# --- list_documents executor ------------------------------------------------------------


async def test_list_documents_executor_paginates_and_reports_total(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    await _seed(
        store,
        embedder,
        [
            Chunk(text=f"doc {i}", source_path=f"{i}.md", page=1, source_hash=f"h{i}", index=0)
            for i in range(5)
        ],
    )

    result = await registry.call("list_documents", {"limit": 2, "offset": 1}, TENANT)

    assert result["total"] == 5
    assert result["limit"] == 2
    assert result["offset"] == 1
    assert len(result["documents"]) == 2


async def test_list_documents_executor_item_includes_modified_at(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    """D44: each `list_documents` item must carry the source file's true `modified_at` — the
    temporal signal an "when was this written/modified" question must be answered from."""
    await _seed(
        store,
        embedder,
        [
            Chunk(
                text="a",
                source_path="a.md",
                page=1,
                source_hash="h1",
                index=0,
                modified_at="2026-01-02T03:04:05+00:00",
            ),
        ],
    )

    result = await registry.call("list_documents", {}, TENANT)

    (doc,) = result["documents"]
    assert doc.modified_at == "2026-01-02T03:04:05+00:00"


async def test_list_documents_executor_metadata_filter(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    await _seed(
        store,
        embedder,
        [
            Chunk(
                text="a",
                source_path="a.md",
                page=1,
                source_hash="h1",
                index=0,
                metadata={"project": "condense"},
            ),
            Chunk(text="b", source_path="b.md", page=1, source_hash="h2", index=0),
        ],
    )

    result = await registry.call("list_documents", {"metadata": {"project": "condense"}}, TENANT)

    assert [d.source_hash for d in result["documents"]] == ["h1"]
    assert result["total"] == 1


class _SpyStore(FakeVectorStore):
    """A :class:`FakeVectorStore` that records every ``ensure_ready`` call (BUG #1 regression).

    ``list_documents``/``get_document_chunks`` must call ``ensure_ready`` themselves — exactly
    like ``search`` already does — so the FIRST call on a fresh process against a not-yet-
    migrated store still succeeds instead of 500ing.
    """

    def __init__(self) -> None:
        super().__init__()
        self.ensure_ready_calls: list[tuple[str, int, str]] = []

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None:
        self.ensure_ready_calls.append((model, dim, tenant))
        await super().ensure_ready(model, dim, tenant)


async def test_list_documents_executor_calls_ensure_ready_on_first_use(
    embedder: FakeEmbedder, settings: Settings
) -> None:
    store = _SpyStore()
    registry = build_tool_registry(embedder, store, settings)

    await registry.call("list_documents", {}, TENANT)

    assert store.ensure_ready_calls == [(MODEL, DIM, TENANT)]


async def test_get_document_chunks_executor_calls_ensure_ready_on_first_use(
    embedder: FakeEmbedder, settings: Settings
) -> None:
    store = _SpyStore()
    registry = build_tool_registry(embedder, store, settings)

    await registry.call("get_document_chunks", {"source_hash": "h1"}, TENANT)

    assert store.ensure_ready_calls == [(MODEL, DIM, TENANT)]


async def test_list_documents_executor_migrates_legacy_libsql_schema_on_first_call(
    tmp_path,
) -> None:
    # Regression for the exact E2E repro: a libSQL DB created before the `metadata` column
    # existed on `chunks`, hit on a FRESH process (ensure_ready() never explicitly called
    # first) — must migrate and succeed, never 500 with "no such column: ...metadata".
    libsql = pytest.importorskip("libsql")
    from sift.adapters.store.libsql import LibSQLStore  # noqa: PLC0415

    db = str(tmp_path / "legacy.db")
    conn = libsql.connect(db)
    conn.execute(
        "CREATE TABLE files (tenant TEXT, content_hash TEXT, path TEXT, indexed_at TEXT, "
        "PRIMARY KEY (tenant, content_hash))"
    )
    conn.execute(
        f"CREATE TABLE chunks (tenant TEXT, source_hash TEXT, idx INTEGER, text TEXT, "
        f"source_path TEXT, page INTEGER, embedding F32_BLOB({DIM}) NOT NULL, "
        "PRIMARY KEY (tenant, source_hash, idx))"  # the pre-metadata schema
    )
    conn.commit()
    conn.close()

    store = LibSQLStore(db)
    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)
    registry = build_tool_registry(FakeEmbedder(DIM), store, settings)
    try:
        # The metadata filter forces the SQL to actually reference the (pre-fix, missing)
        # column — this is the shape that 500'd before ensure_ready() ran the ALTER migration.
        result = await registry.call("list_documents", {"metadata": {"k": "v"}}, TENANT)
        assert result["documents"] == []
    finally:
        await store.aclose()


async def test_get_document_chunks_executor_migrates_legacy_libsql_schema_on_first_call(
    tmp_path,
) -> None:
    # Regression for the exact E2E repro ("no such column: c.metadata"): a legacy chunks table
    # hit on a fresh process via get_document_chunks (never search/ingest first).
    libsql = pytest.importorskip("libsql")
    from sift.adapters.store.libsql import LibSQLStore  # noqa: PLC0415

    db = str(tmp_path / "legacy_chunks.db")
    conn = libsql.connect(db)
    conn.execute(
        "CREATE TABLE files (tenant TEXT, content_hash TEXT, path TEXT, indexed_at TEXT, "
        "PRIMARY KEY (tenant, content_hash))"
    )
    conn.execute(
        "INSERT INTO files (tenant, content_hash, path, indexed_at) VALUES (?, ?, ?, ?)",
        (TENANT, "h1", "a.md", "2026-01-01T00:00:00"),
    )
    conn.execute(
        f"CREATE TABLE chunks (tenant TEXT, source_hash TEXT, idx INTEGER, text TEXT, "
        f"source_path TEXT, page INTEGER, embedding F32_BLOB({DIM}) NOT NULL, "
        "PRIMARY KEY (tenant, source_hash, idx))"  # the pre-metadata schema
    )
    conn.execute(
        "INSERT INTO chunks (tenant, source_hash, idx, text, source_path, page, embedding) "
        "VALUES (?, ?, ?, ?, ?, ?, vector32(?))",
        (TENANT, "h1", 0, "legacy text", "a.md", 1, "[" + ",".join(["0.0"] * DIM) + "]"),
    )
    conn.commit()
    conn.close()

    store = LibSQLStore(db)
    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)
    registry = build_tool_registry(FakeEmbedder(DIM), store, settings)
    try:
        chunks = await registry.call("get_document_chunks", {"source_hash": "h1"}, TENANT)
        assert [c.text for c in chunks] == ["legacy text"]
    finally:
        await store.aclose()


async def test_list_documents_executor_degrades_when_store_unsupported() -> None:
    class _BareStore:
        async def ensure_ready(self, model: str, dim: int, tenant: str) -> None: ...

        async def upsert(self, chunks, tenant: str) -> None: ...

        async def search(self, vector: Vector, k: int, tenant: str, filters=None) -> list[Hit]:
            return []

        async def known_hashes(self, tenant: str) -> set[str]:
            return set()

    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)
    registry = build_tool_registry(FakeEmbedder(DIM), _BareStore(), settings)  # type: ignore[arg-type]

    result = await registry.call("list_documents", {}, TENANT)

    assert result == {"documents": [], "total": 0, "limit": 100, "offset": 0}


# --- get_document_chunks executor --------------------------------------------------------


async def test_get_document_chunks_executor_returns_ordered_chunks(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    await _seed(
        store,
        embedder,
        [
            Chunk(text="third", source_path="a.md", page=1, source_hash="h1", index=2),
            Chunk(text="first", source_path="a.md", page=1, source_hash="h1", index=0),
            Chunk(text="second", source_path="a.md", page=1, source_hash="h1", index=1),
        ],
    )

    chunks = await registry.call("get_document_chunks", {"source_hash": "h1"}, TENANT)

    assert [c.text for c in chunks] == ["first", "second", "third"]


async def test_get_document_chunks_executor_includes_modified_at_and_metadata(
    registry: ToolRegistry, store: FakeVectorStore, embedder: FakeEmbedder
) -> None:
    """D44: each chunk returned by `get_document_chunks` must carry `modified_at` + `metadata`."""
    await _seed(
        store,
        embedder,
        [
            Chunk(
                text="dated",
                source_path="a.md",
                page=1,
                source_hash="h1",
                index=0,
                modified_at="2026-04-05T06:07:08+00:00",
                metadata={"project": "condense"},
            ),
        ],
    )

    (chunk,) = await registry.call("get_document_chunks", {"source_hash": "h1"}, TENANT)

    assert chunk.modified_at == "2026-04-05T06:07:08+00:00"
    assert chunk.metadata == {"project": "condense"}


async def test_get_document_chunks_executor_degrades_when_store_unsupported() -> None:
    class _BareStore:
        async def ensure_ready(self, model: str, dim: int, tenant: str) -> None: ...

        async def upsert(self, chunks, tenant: str) -> None: ...

        async def search(self, vector: Vector, k: int, tenant: str, filters=None) -> list[Hit]:
            return []

        async def known_hashes(self, tenant: str) -> set[str]:
            return set()

    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)
    registry = build_tool_registry(FakeEmbedder(DIM), _BareStore(), settings)  # type: ignore[arg-type]

    assert await registry.call("get_document_chunks", {"source_hash": "h1"}, TENANT) == []


# --- D44: temporal fields round-trip through a REAL libSQL store, not just the fake -----------
#
# The fake carries `modified_at`/`metadata` straight through in-memory, which can't catch a
# column dropped from a SELECT or missing from a JOIN. These mirror the fake-store executor
# tests above against a real `tmp_path` libSQL DB with a known mtime.


async def test_list_documents_executor_item_includes_modified_at_against_libsql(
    tmp_path,
) -> None:
    libsql = pytest.importorskip("libsql")  # noqa: F841
    from sift.adapters.store.libsql import LibSQLStore  # noqa: PLC0415

    db = str(tmp_path / "temporal_list.db")
    store = LibSQLStore(db)
    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)
    registry = build_tool_registry(FakeEmbedder(DIM), store, settings)
    try:
        await _seed(
            store,
            FakeEmbedder(DIM),
            [
                Chunk(
                    text="a",
                    source_path="a.md",
                    page=1,
                    source_hash="h1",
                    index=0,
                    modified_at="2026-01-02T03:04:05+00:00",
                ),
            ],
        )

        result = await registry.call("list_documents", {}, TENANT)

        (doc,) = result["documents"]
        assert doc.modified_at == "2026-01-02T03:04:05+00:00"
        assert doc.indexed_at is not None
    finally:
        await store.aclose()


async def test_get_document_chunks_executor_includes_modified_at_and_metadata_against_libsql(
    tmp_path,
) -> None:
    libsql = pytest.importorskip("libsql")  # noqa: F841
    from sift.adapters.store.libsql import LibSQLStore  # noqa: PLC0415

    db = str(tmp_path / "temporal_chunks.db")
    store = LibSQLStore(db)
    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)
    registry = build_tool_registry(FakeEmbedder(DIM), store, settings)
    try:
        await _seed(
            store,
            FakeEmbedder(DIM),
            [
                Chunk(
                    text="dated",
                    source_path="a.md",
                    page=1,
                    source_hash="h1",
                    index=0,
                    modified_at="2026-04-05T06:07:08+00:00",
                    metadata={"project": "condense"},
                ),
            ],
        )

        (chunk,) = await registry.call("get_document_chunks", {"source_hash": "h1"}, TENANT)

        assert chunk.modified_at == "2026-04-05T06:07:08+00:00"
        assert chunk.metadata == {"project": "condense"}
    finally:
        await store.aclose()


async def test_search_executor_hit_includes_modified_at_and_metadata_against_libsql(
    tmp_path,
) -> None:
    libsql = pytest.importorskip("libsql")  # noqa: F841
    from sift.adapters.store.libsql import LibSQLStore  # noqa: PLC0415

    db = str(tmp_path / "temporal_search.db")
    store = LibSQLStore(db)
    settings = Settings(ingest_token="t", embed_dim=DIM, embed_model=MODEL)
    embedder = FakeEmbedder(DIM)
    registry = build_tool_registry(embedder, store, settings)
    try:
        await _seed(
            store,
            embedder,
            [
                Chunk(
                    text="gamma one",
                    source_path="g.md",
                    page=1,
                    source_hash="hg",
                    index=0,
                    modified_at="2026-03-04T05:06:07+00:00",
                    metadata={"project": "condense"},
                ),
            ],
        )

        (hit,) = await registry.call("search", {"query": "gamma one"}, TENANT)

        assert hit.modified_at == "2026-03-04T05:06:07+00:00"
        assert hit.metadata == {"project": "condense"}
    finally:
        await store.aclose()
