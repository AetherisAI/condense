"""TestClient coverage for ``POST /v1/documents`` — JSON ingest (offline, fakes only).

The non-multipart sibling of the existing ``POST /ingest`` (see ``test_routes.py``): one inline
text document per request, going through the same :class:`~sift.pipelines.ingest.IngestPipeline`
seam, so it must return the identical ``IngestFileResult`` shape and honor the same auth,
dedup, and metadata-threading behavior. Uses a real :class:`~sift.pipelines.ingest.IngestPipeline`
wired to :class:`~sift.adapters.store.fake.FakeVectorStore` (not the ``_StubIngest`` placeholder)
so metadata persistence + searchability can actually be asserted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore
from sift.api.deps import get_container
from sift.api.main import app
from sift.config import Settings, get_settings
from sift.core.hashing import content_hash
from sift.core.types import Chunk, Document, Page
from sift.factory import Container, build_container
from sift.pipelines.ingest import IngestPipeline

_TOKEN = "t"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


class _WholeFileParser:
    """Bytes → a single-page Document (whole file as one page) — minimal ``Parser`` test double."""

    async def parse(self, data: bytes, filename: str) -> Document:
        return Document(
            path=filename,
            content_hash=content_hash(data),
            pages=(Page(number=1, text=data.decode()),),
        )


class _WholeFileChunker:
    """One Chunk per Document (no splitting) — minimal ``Chunker`` test double."""

    async def chunk(self, doc: Document) -> list[Chunk]:
        text = doc.pages[0].text
        return [
            Chunk(text=text, source_path=doc.path, page=1, source_hash=doc.content_hash, index=0)
        ]


def _real_ingest_container() -> tuple[Container, FakeVectorStore, FakeEmbedder]:
    """A wired container whose ``ingest`` is a real :class:`IngestPipeline` over a fake store —
    unlike the default container's ``_StubIngest`` placeholder, this one actually persists."""
    settings = Settings(ingest_token=_TOKEN)
    store = FakeVectorStore()
    embedder = FakeEmbedder(settings.embed_dim)
    pipeline = IngestPipeline(
        _WholeFileParser(),
        _WholeFileChunker(),
        embedder,
        store,
        model=settings.embed_model,
        dim=settings.embed_dim,
    )
    container = replace(build_container(settings), ingest=pipeline, store=store)
    return container, store, embedder


@pytest.fixture(autouse=True)
def _ingest_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lifespan builds the real Container via ``get_settings()``; supply the required token."""
    monkeypatch.setenv("INGEST_TOKEN", _TOKEN)
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient whose ``get_container`` is overridden with a real-ingest fake container."""
    container, _, _ = _real_ingest_container()
    app.dependency_overrides[get_container] = lambda: container
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_json_ingest_requires_auth(client: TestClient) -> None:
    response = client.post("/v1/documents", json={"text": "hello world"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_json_ingest_rejects_empty_text(client: TestClient) -> None:
    response = client.post("/v1/documents", json={"text": ""}, headers=_AUTH)

    assert response.status_code == 422


def test_json_ingest_rejects_text_over_parse_max_chars(client: TestClient) -> None:
    # D40 amendment: `text`'s ceiling is tied to `Settings.parse_max_chars` (the same
    # post-parse guardrail every OTHER ingest path enforces, D39) so an oversized inline JSON
    # document 422s up front instead of being accepted here and only failing deep inside the
    # parse pipeline.
    limit = get_settings().parse_max_chars
    response = client.post("/v1/documents", json={"text": "x" * (limit + 1)}, headers=_AUTH)

    assert response.status_code == 422


def test_json_ingest_accepts_text_at_parse_max_chars(client: TestClient) -> None:
    limit = get_settings().parse_max_chars
    response = client.post("/v1/documents", json={"text": "x" * limit}, headers=_AUTH)

    assert response.status_code == 200


def test_json_ingest_indexes_with_metadata_persisted_and_searchable() -> None:
    container, store, embedder = _real_ingest_container()
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/v1/documents",
                json={
                    "text": "alpha passage",
                    "filename": "note.txt",
                    "metadata": {"topic": "test"},
                },
                headers=_AUTH,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "note.txt"
    assert body["status"] == "indexed"
    assert body["chunks"] == 1
    assert body["content_hash"] == content_hash(b"alpha passage")

    async def _search():
        (vector,) = await embedder.embed(["alpha passage"])
        return await store.search(vector, 5, "default")

    (hit,) = asyncio.run(_search())
    assert hit.metadata == {"topic": "test"}


def test_json_ingest_default_filename_derived_from_content_hash() -> None:
    container, _, _ = _real_ingest_container()
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/v1/documents", json={"text": "no filename given"}, headers=_AUTH
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    digest8 = content_hash(b"no filename given")[:8]
    assert body["path"] == f"note-{digest8}.txt"


def test_json_ingest_dedups_identical_text() -> None:
    container, _, _ = _real_ingest_container()
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as test_client:
            first = test_client.post(
                "/v1/documents", json={"text": "same content", "filename": "a.txt"}, headers=_AUTH
            )
            second = test_client.post(
                "/v1/documents", json={"text": "same content", "filename": "b.txt"}, headers=_AUTH
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert first.json()["status"] == "indexed"
    assert second.status_code == 200
    # Same content_hash as the first (dedup keys on bytes, not filename) → skipped.
    assert second.json()["status"] == "skipped_dedup"
    assert second.json()["content_hash"] == first.json()["content_hash"]


def test_json_ingest_invalid_modified_at_is_dropped_not_stored() -> None:
    container, store, embedder = _real_ingest_container()
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/v1/documents",
                json={
                    "text": "beta content",
                    "filename": "bad.txt",
                    "modified_at": "corrupted-not-a-date",
                },
                headers=_AUTH,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "indexed"

    async def _search():
        (vector,) = await embedder.embed(["beta content"])
        return await store.search(vector, 5, "default")

    (hit,) = asyncio.run(_search())
    assert hit.modified_at is None  # garbage value dropped, never stored raw (A1)
