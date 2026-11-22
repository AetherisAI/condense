"""Tests for :class:`~sift.adapters.store.libsql.LibSQLStore` (parity with FakeVectorStore).

Each test runs against a fresh temp-file libSQL DB (``tmp_path``) and tears the store down via
``aclose()``. ``pytest-asyncio`` auto mode runs the ``async def`` tests. Vectors round-trip through
``F32_BLOB``, so exact-match score asserts use ``rel_tol=1e-4`` (looser than the fake's ``1e-9``).
"""

from __future__ import annotations

import math
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

import pytest

libsql = pytest.importorskip("libsql")

from sift.adapters.embedding.fake import FakeEmbedder  # noqa: E402
from sift.adapters.store.libsql import LibSQLStore  # noqa: E402
from sift.core.errors import ModelPinMismatch, SiftError  # noqa: E402
from sift.core.ports import VectorStore  # noqa: E402
from sift.core.types import Chunk, SearchFilters  # noqa: E402

MODEL = "bge-m3"
DIM = 8
TENANT = "default"


@pytest.fixture
async def store(tmp_path) -> AsyncIterator[LibSQLStore]:
    impl = LibSQLStore(str(tmp_path / "sift.db"))
    try:
        yield impl
    finally:
        await impl.aclose()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder(dim=DIM)


async def _embedded(embedder: FakeEmbedder, chunk: Chunk) -> Chunk:
    (vector,) = await embedder.embed([chunk.text])
    return replace(chunk, vector=vector)


async def test_satisfies_vector_store_port(store: LibSQLStore) -> None:
    assert isinstance(store, VectorStore)


async def test_ensure_ready_pins_then_accepts_same_pin(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.ensure_ready(MODEL, DIM, TENANT)  # idempotent — must not raise
    assert await store.known_hashes(TENANT) == set()


async def test_ensure_ready_rejects_model_or_dim_mismatch(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    with pytest.raises(ModelPinMismatch):
        await store.ensure_ready("other-model", DIM, TENANT)
    with pytest.raises(ModelPinMismatch):
        await store.ensure_ready(MODEL, DIM + 1, TENANT)


async def test_upsert_then_search_returns_best_with_citation(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(text="the sky is blue", source_path="a.md", page=1, source_hash="h1", index=0),
        Chunk(text="grass is green", source_path="b.md", page=2, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["the sky is blue"])
    hits = await store.search(query, 5, TENANT)

    assert hits
    best = hits[0]
    assert best.source_path == "a.md"
    assert best.page == 1
    assert best.text == "the sky is blue"
    assert best.source_hash == "h1"
    assert best.index == 0
    assert math.isclose(best.score, 1.0, rel_tol=1e-4)


async def test_search_round_trips_modified_at(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(
        text="versioned passage",
        source_path="v.md",
        page=1,
        source_hash="hv",
        index=0,
        modified_at="2026-02-03T04:05:06+00:00",
    )
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (query,) = await embedder.embed(["versioned passage"])
    (hit,) = await store.search(query, 5, TENANT)
    assert hit.modified_at == "2026-02-03T04:05:06+00:00"  # the recency signal survives the join
    assert hit.indexed_at is not None  # ingest-time fallback is still stamped


async def test_search_round_trips_metadata(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(
        text="tagged passage",
        source_path="m.md",
        page=1,
        source_hash="hm",
        index=0,
        metadata={"author": "alice", "kind": "note"},
    )
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (query,) = await embedder.embed(["tagged passage"])
    (hit,) = await store.search(query, 5, TENANT)
    assert hit.metadata == {"author": "alice", "kind": "note"}  # survives the JSON round-trip


async def test_search_returns_none_metadata_when_absent(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="no tags here", source_path="n.md", page=1, source_hash="hn", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (query,) = await embedder.embed(["no tags here"])
    (hit,) = await store.search(query, 5, TENANT)
    assert hit.metadata is None


async def test_ensure_ready_migrates_legacy_chunks_table(tmp_path) -> None:
    # A database created before ``metadata`` existed on ``chunks``: ensure_ready must ALTER it
    # in, not crash.
    db = str(tmp_path / "legacy_chunks.db")
    conn = libsql.connect(db)
    conn.execute(
        f"CREATE TABLE chunks (tenant TEXT, source_hash TEXT, idx INTEGER, text TEXT, "
        f"source_path TEXT, page INTEGER, embedding F32_BLOB({DIM}) NOT NULL, "
        "PRIMARY KEY (tenant, source_hash, idx))"  # the pre-metadata schema
    )
    conn.commit()
    conn.close()

    store = LibSQLStore(db)
    embedder = FakeEmbedder(dim=DIM)
    try:
        await store.ensure_ready(MODEL, DIM, TENANT)  # migrates: adds the metadata column
        chunk = Chunk(
            text="y", source_path="y.md", page=1, source_hash="hy", index=0, metadata={"k": "v"}
        )
        await store.upsert([await _embedded(embedder, chunk)], TENANT)
        (query,) = await embedder.embed(["y"])
        (hit,) = await store.search(query, 5, TENANT)
        assert hit.metadata == {"k": "v"}
    finally:
        await store.aclose()


async def test_ensure_ready_migrates_legacy_files_table(tmp_path) -> None:
    # A database created before ``modified_at`` existed: ensure_ready must ALTER it in, not crash.
    db = str(tmp_path / "legacy.db")
    conn = libsql.connect(db)
    conn.execute(
        "CREATE TABLE files (tenant TEXT, content_hash TEXT, path TEXT, indexed_at TEXT, "
        "PRIMARY KEY (tenant, content_hash))"  # the pre-modified_at schema
    )
    conn.commit()
    conn.close()

    store = LibSQLStore(db)
    embedder = FakeEmbedder(dim=DIM)
    try:
        await store.ensure_ready(MODEL, DIM, TENANT)  # migrates: adds the modified_at column
        chunk = Chunk(
            text="x", source_path="x.md", page=1, source_hash="hx", index=0, modified_at="2026-05"
        )
        await store.upsert([await _embedded(embedder, chunk)], TENANT)
        (query,) = await embedder.embed(["x"])
        (hit,) = await store.search(query, 5, TENANT)
        assert hit.modified_at == "2026-05"
    finally:
        await store.aclose()


async def test_search_honors_k(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(text=f"doc {i}", source_path=f"{i}.md", page=1, source_hash=f"h{i}", index=0)
        for i in range(5)
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["doc 2"])
    assert len(await store.search(query, 3, TENANT)) == 3


async def test_search_empty_when_no_rows(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    (query,) = await embedder.embed(["nothing here"])
    assert await store.search(query, 5, TENANT) == []


async def test_tenant_isolation(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, "tenant-a")
    chunk = Chunk(text="only in a", source_path="a.md", page=1, source_hash="ha", index=0)
    await store.upsert([await _embedded(embedder, chunk)], "tenant-a")

    await store.ensure_ready(MODEL, DIM, "tenant-b")
    (query,) = await embedder.embed(["only in a"])
    assert await store.search(query, 5, "tenant-b") == []
    assert await store.known_hashes("tenant-b") == set()

    assert await store.known_hashes("tenant-a") == {"ha"}


async def test_known_hashes_returns_ingested_hash(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="hello", source_path="x.md", page=1, source_hash="hx", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)
    assert await store.known_hashes(TENANT) == {"hx"}


async def test_idempotent_reupsert_keeps_row_count_and_updates_text(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    original = Chunk(text="v1", source_path="a.md", page=1, source_hash="h1", index=0)
    await store.upsert([await _embedded(embedder, original)], TENANT)
    await store.upsert([await _embedded(embedder, original)], TENANT)  # identical re-upsert

    (query,) = await embedder.embed(["v1"])
    assert len(await store.search(query, 100, TENANT)) == 1  # row count stable

    updated = replace(original, text="v2")
    await store.upsert([await _embedded(embedder, updated)], TENANT)

    hits = await store.search(query, 100, TENANT)
    assert len(hits) == 1  # same (source_hash, index) key — no new row
    assert hits[0].text == "v2"  # changed text persisted


async def test_upsert_before_ensure_ready_raises_sift_error(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)
    with pytest.raises(SiftError):
        await store.upsert([await _embedded(embedder, chunk)], TENANT)


async def test_read_paths_before_ensure_ready_report_empty_store(store: LibSQLStore) -> None:
    """A fresh DB has no schema yet — the agent dedups by reading *before* the first ingest.

    ``known_hashes``/``list_documents`` must report an empty store rather than raising
    ``no such table: files`` (which surfaced as a 500 on ``/ingest/manifest`` + ``/documents``).
    """
    assert await store.known_hashes(TENANT) == set()
    assert await store.list_documents(TENANT) == []


async def test_upsert_none_vector_raises_value_error(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)  # vector None
    with pytest.raises(ValueError):
        await store.upsert([chunk], TENANT)


async def test_upsert_wrong_dim_vector_raises_value_error(store: LibSQLStore) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    wrong = FakeEmbedder(dim=DIM + 1)
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)
    with pytest.raises(ValueError):
        await store.upsert([await _embedded(wrong, chunk)], TENANT)


# --- document-admin seam (SupportsDocumentAdmin) parity -----------------------


async def test_list_documents_lists_ingested_files_with_chunk_counts(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(text="a one", source_path="a.md", page=1, source_hash="h1", index=0),
        Chunk(text="a two", source_path="a.md", page=1, source_hash="h1", index=1),
        Chunk(text="b one", source_path="b.md", page=1, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    docs = {d.source_hash: d for d in await store.list_documents(TENANT)}
    assert set(docs) == {"h1", "h2"}
    assert docs["h1"].source_path == "a.md"
    assert docs["h1"].chunks == 2  # two chunk rows aggregated under one file
    assert docs["h2"].source_path == "b.md"
    assert docs["h2"].chunks == 1


async def test_list_documents_includes_modified_at_and_indexed_at(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    """The documents-listing path must surface the file's true mtime (temporal-knowledge
    plumbing) — ``indexed_at`` (when the store wrote the row) rides along too since the
    ``files`` table already carries it for free."""
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(
        text="a one",
        source_path="a.md",
        page=1,
        source_hash="h1",
        index=0,
        modified_at="2026-02-03T04:05:06+00:00",
    )
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (doc,) = await store.list_documents(TENANT)

    assert doc.modified_at == "2026-02-03T04:05:06+00:00"
    assert doc.indexed_at is not None  # a real ISO-8601 timestamp, stamped at upsert time


async def test_list_documents_modified_at_is_none_when_never_provided(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="a one", source_path="a.md", page=1, source_hash="h1", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (doc,) = await store.list_documents(TENANT)

    assert doc.modified_at is None


async def test_delete_document_removes_chunks_and_file_and_returns_count(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(text="a one", source_path="a.md", page=1, source_hash="h1", index=0),
        Chunk(text="a two", source_path="a.md", page=1, source_hash="h1", index=1),
        Chunk(text="b one", source_path="b.md", page=1, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    removed = await store.delete_document("h1", TENANT)
    assert removed == 2  # both of h1's chunk rows counted and deleted

    remaining = await store.list_documents(TENANT)
    assert [d.source_hash for d in remaining] == ["h2"]  # h1 gone from the listing
    assert await store.known_hashes(TENANT) == {"h2"}  # files row dropped → re-ingest re-indexes

    (query,) = await embedder.embed(["a one"])
    hits = await store.search(query, 100, TENANT)
    assert all(hit.source_hash != "h1" for hit in hits)  # no h1 chunk rows survive


async def test_delete_document_unknown_hash_is_noop_and_returns_zero(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="keep me", source_path="k.md", page=1, source_hash="hk", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    assert await store.delete_document("does-not-exist", TENANT) == 0
    assert await store.known_hashes(TENANT) == {"hk"}  # existing doc untouched


# --- search filters: metadata equality + since/until ------


async def test_search_metadata_filter_narrows_via_json_extract(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(
            text="alpha one",
            source_path="a.md",
            page=1,
            source_hash="h1",
            index=0,
            metadata={"project": "condense"},
        ),
        Chunk(
            text="alpha two",
            source_path="b.md",
            page=1,
            source_hash="h2",
            index=0,
            metadata={"project": "other"},
        ),
        Chunk(text="alpha three", source_path="c.md", page=1, source_hash="h3", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["alpha"])
    hits = await store.search(query, 10, TENANT, SearchFilters(metadata={"project": "condense"}))

    assert [hit.source_path for hit in hits] == ["a.md"]


async def test_search_since_until_filter_narrows_by_modified_at(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
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
        Chunk(text="beta undated", source_path="u.md", page=1, source_hash="hu", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    (query,) = await embedder.embed(["beta"])
    hits = await store.search(query, 10, TENANT, SearchFilters(since="2026-03-01"))

    assert [hit.source_path for hit in hits] == ["new.md"]

    hits_bounded = await store.search(
        query, 10, TENANT, SearchFilters(since="2026-01-01", until="2026-03-01")
    )
    assert [hit.source_path for hit in hits_bounded] == ["old.md"]


async def test_search_no_filters_is_unchanged(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="gamma", source_path="g.md", page=1, source_hash="hg", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (query,) = await embedder.embed(["gamma"])
    hits = await store.search(query, 5, TENANT)  # no filters arg — backward compatible

    assert [hit.source_path for hit in hits] == ["g.md"]


# --- get_chunks (SupportsChunkAccess seam) ------------------------------------


async def test_get_chunks_returns_ordered_chunks_for_one_document(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(text="third", source_path="a.md", page=1, source_hash="h1", index=2),
        Chunk(text="first", source_path="a.md", page=1, source_hash="h1", index=0),
        Chunk(
            text="second",
            source_path="a.md",
            page=1,
            source_hash="h1",
            index=1,
            metadata={"k": "v"},
        ),
        Chunk(text="other doc", source_path="b.md", page=1, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    result = await store.get_chunks("h1", TENANT)

    assert [c.text for c in result] == ["first", "second", "third"]
    assert all(c.source_hash == "h1" for c in result)
    assert result[1].metadata == {"k": "v"}  # metadata round-trips through the chunk-access seam


async def test_get_chunks_includes_modified_at(store: LibSQLStore, embedder: FakeEmbedder) -> None:
    """Each chunk carries its parent file's ``modified_at`` — the temporal signal a tool
    consumer needs to answer "when was this written/modified" honestly."""
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(
        text="dated",
        source_path="a.md",
        page=1,
        source_hash="h1",
        index=0,
        modified_at="2026-05-06T07:08:09+00:00",
    )
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    (result,) = await store.get_chunks("h1", TENANT)

    assert result.modified_at == "2026-05-06T07:08:09+00:00"


async def test_get_chunks_unknown_hash_returns_empty(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunk = Chunk(text="x", source_path="x.md", page=1, source_hash="hx", index=0)
    await store.upsert([await _embedded(embedder, chunk)], TENANT)

    assert await store.get_chunks("does-not-exist", TENANT) == []


async def test_get_chunks_before_ensure_ready_returns_empty(store: LibSQLStore) -> None:
    # Fresh DB, no schema yet — must degrade to "no chunks", never a table-missing crash.
    assert await store.get_chunks("anything", TENANT) == []


# --- list_documents metadata filter (SupportsDocumentAdmin) -------------


async def test_list_documents_metadata_filter_narrows_via_exists_subquery(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        Chunk(
            text="a one",
            source_path="a.md",
            page=1,
            source_hash="h1",
            index=0,
            metadata={"project": "condense"},
        ),
        Chunk(text="b one", source_path="b.md", page=1, source_hash="h2", index=0),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    docs = await store.list_documents(TENANT, metadata={"project": "condense"})

    assert [d.source_hash for d in docs] == ["h1"]


# --- keyword search (SupportsKeywordSearch) ------------------------------


def _chunk(text: str, source_hash: str, index: int = 0, **extra: Any) -> Chunk:
    return Chunk(
        text=text,
        source_path=f"{source_hash}.md",
        page=1,
        source_hash=source_hash,
        index=index,
        **extra,
    )


async def _keyword_hashes(
    store: LibSQLStore, embedder: FakeEmbedder, query: str, **kw: Any
) -> list[str]:
    (vector,) = await embedder.embed([query])
    return [hit.source_hash for hit in await store.keyword_search(query, vector, 10, TENANT, **kw)]


async def test_satisfies_keyword_search_capability(store: LibSQLStore) -> None:
    from sift.pipelines.retrieval import SupportsKeywordSearch

    assert isinstance(store, SupportsKeywordSearch)


async def test_keyword_search_ranks_by_matching_words(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        _chunk("FrostyGoop sent Modbus commands over TCP port 502", "h1"),
        _chunk("Modbus is an industrial protocol", "h2"),
        _chunk("Spearphishing attachments deliver malware", "h3"),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    # h1 shares three words, h2 one, h3 none: h3 isn't a match at all.
    assert await _keyword_hashes(store, embedder, "Which device used Modbus port 502?") == [
        "h1",
        "h2",
    ]
    assert await _keyword_hashes(store, embedder, "frostygoop") == ["h1"]


async def test_keyword_search_matches_identifiers_the_tokenizer_splits(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    chunks = [
        _chunk("T1566.001 Spearphishing Attachment", "h1"),
        _chunk("T1566 Phishing, and sub-technique 001 elsewhere", "h2"),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)

    # "t1566.001" is one quoted phrase: both parts, adjacent, so h1 ranks first.
    assert (await _keyword_hashes(store, embedder, "what is T1566.001"))[0] == "h1"


async def test_keyword_search_scores_hits_by_cosine_similarity(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.upsert([await _embedded(embedder, _chunk("exact passage text", "h1"))], TENANT)

    (vector,) = await embedder.embed(["exact passage text"])
    (hit,) = await store.keyword_search("exact passage text", vector, 5, TENANT)
    assert math.isclose(hit.score, 1.0, rel_tol=1e-4)  # cosine, like search(), not BM25


async def test_keyword_search_treats_operators_and_punctuation_as_text(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.upsert([await _embedded(embedder, _chunk("NEAR the OR gate", "h1"))], TENANT)

    # FTS5 syntax in user input must not raise or change the query's meaning.
    assert await _keyword_hashes(store, embedder, 'gate" OR text:* NEAR(') == ["h1"]
    assert await _keyword_hashes(store, embedder, "?!... ---") == []  # no words, no query


async def test_keyword_search_keeps_stopwords_when_nothing_else_is_left(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.upsert([await _embedded(embedder, _chunk("to be or not to be", "h1"))], TENANT)

    assert await _keyword_hashes(store, embedder, "to be") == ["h1"]


async def test_keyword_search_respects_tenant_and_filters(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.ensure_ready(MODEL, DIM, "other")
    chunks = [
        _chunk("zephyrium report", "h1", metadata={"kind": "report"}),
        _chunk("zephyrium memo", "h2", metadata={"kind": "memo"}),
    ]
    await store.upsert([await _embedded(embedder, c) for c in chunks], TENANT)
    await store.upsert([await _embedded(embedder, _chunk("zephyrium elsewhere", "h3"))], "other")

    assert sorted(await _keyword_hashes(store, embedder, "zephyrium")) == ["h1", "h2"]
    narrowed = await _keyword_hashes(
        store, embedder, "zephyrium", filters=SearchFilters(metadata={"kind": "memo"})
    )
    assert narrowed == ["h2"]


async def test_keyword_index_follows_updates_and_deletes(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.upsert([await _embedded(embedder, _chunk("original wording", "h1"))], TENANT)
    await store.upsert([await _embedded(embedder, _chunk("revised wording", "h1"))], TENANT)

    assert await _keyword_hashes(store, embedder, "original") == []
    assert await _keyword_hashes(store, embedder, "revised") == ["h1"]

    await store.delete_document("h1", TENANT)
    assert await _keyword_hashes(store, embedder, "revised wording") == []


async def test_ensure_ready_indexes_chunks_stored_before_keyword_search(tmp_path) -> None:
    # A database written by a version without the keyword index: the first ensure_ready
    # creates it and indexes what's already there.
    db = str(tmp_path / "pre_fts.db")
    embedder = FakeEmbedder(dim=DIM)
    old = LibSQLStore(db)
    try:
        await old.ensure_ready(MODEL, DIM, TENANT)
        await old.upsert([await _embedded(embedder, _chunk("legacy passage", "h1"))], TENANT)
    finally:
        await old.aclose()
    conn = libsql.connect(db)
    for name in ("chunks_fts_insert", "chunks_fts_delete", "chunks_fts_update"):
        conn.execute(f"DROP TRIGGER {name}")
    conn.execute("DROP TABLE chunks_fts")
    conn.commit()
    conn.close()

    store = LibSQLStore(db)
    try:
        await store.ensure_ready(MODEL, DIM, TENANT)
        assert await _keyword_hashes(store, embedder, "legacy") == ["h1"]
    finally:
        await store.aclose()


async def test_keyword_search_before_ensure_ready_returns_empty(
    store: LibSQLStore, embedder: FakeEmbedder
) -> None:
    assert await _keyword_hashes(store, embedder, "anything") == []


async def test_store_without_fts5_falls_back_to_vector_search(
    store: LibSQLStore, embedder: FakeEmbedder, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stand in for a libSQL server built without FTS5: creating the index fails with
    # "no such module", and the store must keep working with vectors alone.
    import sift.adapters.store.libsql as libsql_store

    monkeypatch.setattr(
        libsql_store, "_DDL_CHUNKS_FTS", "CREATE VIRTUAL TABLE chunks_fts USING not_fts5(text)"
    )
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.upsert([await _embedded(embedder, _chunk("still searchable", "h1"))], TENANT)

    assert await _keyword_hashes(store, embedder, "searchable") == []
    (vector,) = await embedder.embed(["still searchable"])
    assert [hit.source_hash for hit in await store.search(vector, 5, TENANT)] == ["h1"]


async def test_failed_index_setup_leaves_no_half_made_index(
    store: LibSQLStore, embedder: FakeEmbedder, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    # The table gets created, then a trigger fails: an index with no triggers would go stale,
    # so it must be dropped and search must carry on with vectors.
    import sift.adapters.store.libsql as libsql_store

    broken = "CREATE TRIGGER chunks_fts_insert AFTER INSERT ON no_such_table BEGIN SELECT 1; END"
    monkeypatch.setattr(libsql_store, "_FTS_TRIGGERS", (broken,))
    await store.ensure_ready(MODEL, DIM, TENANT)
    await store.upsert([await _embedded(embedder, _chunk("still searchable", "h1"))], TENANT)

    assert await _keyword_hashes(store, embedder, "searchable") == []
    (vector,) = await embedder.embed(["still searchable"])
    assert [hit.source_hash for hit in await store.search(vector, 5, TENANT)] == ["h1"]
    conn = libsql.connect(str(tmp_path / "sift.db"))  # the store fixture's database
    leftovers = conn.execute(libsql_store._FTS_TABLE_EXISTS).fetchall()
    conn.close()
    assert leftovers == []
