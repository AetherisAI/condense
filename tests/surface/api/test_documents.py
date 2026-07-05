"""TestClient coverage for the document-admin routes (offline, fakes only).

``GET /documents`` lists the tenant's ingested source files — one row per file, aggregated from
its chunks — and ``DELETE /documents/{source_hash}`` drops one; both sit behind the single
``resolve_tenant`` bearer chokepoint (a missing token → 401). When the configured store does not
implement the :class:`~sift.pipelines.documents.SupportsDocumentAdmin` seam the listing degrades
to ``supported=false`` and the delete returns 501 — exercised here with a store that lacks those
methods. The container is the wired fakes from :func:`~sift.factory.build_container`, injected via
``app.dependency_overrides`` so no network is touched.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from sift.adapters.embedding.fake import FakeEmbedder
from sift.api.deps import get_container
from sift.api.main import app
from sift.config import Settings, get_settings
from sift.core.types import Chunk, Hit, Vector
from sift.factory import Container, build_container

_TOKEN = "t"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}

# Two source files with distinct hashes: cats.md (two chunks) and dogs.md (one) — "h_cats" sorts
# before "h_dogs", so the listing order is deterministic. cats.md carries a known modified_at
# (D44) so the API-level round-trip can be asserted; dogs.md has none (modified_at stays null).
_MODIFIED_AT = "2026-02-03T04:05:06+00:00"
_SEED: tuple[tuple[str, str, int, str | None], ...] = (
    ("cats.md", "h_cats", 0, _MODIFIED_AT),
    ("cats.md", "h_cats", 1, _MODIFIED_AT),
    ("dogs.md", "h_dogs", 0, None),
)


def _seeded_container() -> Container:
    """The default fake container with the ``_SEED`` chunks indexed for ``default``."""
    settings = Settings(ingest_token=_TOKEN)
    container = build_container(settings)
    store = container.store
    embedder = FakeEmbedder(settings.embed_dim)

    async def _seed() -> None:
        await store.ensure_ready(settings.embed_model, settings.embed_dim, "default")
        for path, source_hash, index, modified_at in _SEED:
            chunk = Chunk(
                text=f"{source_hash}:{index}",
                source_path=path,
                page=1,
                source_hash=source_hash,
                index=index,
                modified_at=modified_at,
            )
            (vector,) = await embedder.embed([chunk.text])
            await store.upsert([replace(chunk, vector=vector)], "default")

    asyncio.run(_seed())
    return container


class _AdminlessStore:
    """A :class:`~sift.core.ports.VectorStore` with no document-admin methods.

    Stands in for a store (e.g. an early libSQL adapter) that has not yet grown the
    :class:`~sift.pipelines.documents.SupportsDocumentAdmin` capability — so the routes must
    degrade instead of calling methods that aren't there.
    """

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None: ...

    async def upsert(self, chunks: Sequence[Chunk], tenant: str) -> None: ...

    async def search(self, vector: Vector, k: int, tenant: str) -> list[Hit]:
        return []

    async def known_hashes(self, tenant: str) -> set[str]:
        return set()


@pytest.fixture(autouse=True)
def _ingest_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The lifespan builds the real Container via ``get_settings()``; supply the required token."""
    monkeypatch.setenv("INGEST_TOKEN", _TOKEN)
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient whose ``get_container`` is overridden with the seeded fake container."""
    container = _seeded_container()
    app.dependency_overrides[get_container] = lambda: container
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_documents_requires_auth(client: TestClient) -> None:
    response = client.get("/documents")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_documents_lists_ingested_files_with_chunk_counts(client: TestClient) -> None:
    response = client.get("/documents", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == "default"
    assert body["supported"] is True
    # One row per source file, sorted by source_hash, with the per-file chunk count aggregated.
    assert [d["source_hash"] for d in body["documents"]] == ["h_cats", "h_dogs"]
    by_hash = {d["source_hash"]: d for d in body["documents"]}
    assert by_hash["h_cats"]["path"] == "cats.md"
    assert by_hash["h_cats"]["chunks"] == 2
    assert by_hash["h_dogs"]["path"] == "dogs.md"
    assert by_hash["h_dogs"]["chunks"] == 1


def test_documents_listing_carries_modified_at(client: TestClient) -> None:
    """D44: `GET /documents` must surface the file's true `modified_at` (or `null` when never
    provided at ingest) — the temporal signal a consumer answers "when was this written" from."""
    response = client.get("/documents", headers=_AUTH)

    assert response.status_code == 200
    by_hash = {d["source_hash"]: d for d in response.json()["documents"]}
    assert by_hash["h_cats"]["modified_at"] == "2026-02-03T04:05:06+00:00"
    assert by_hash["h_dogs"]["modified_at"] is None


def test_delete_document_removes_chunks_then_unlisted(client: TestClient) -> None:
    deletion = client.delete("/documents/h_cats", headers=_AUTH)

    assert deletion.status_code == 200
    body = deletion.json()
    assert body == {"tenant": "default", "source_hash": "h_cats", "deleted_chunks": 2}

    # The deleted file is gone from a later listing; its sibling remains.
    remaining = client.get("/documents", headers=_AUTH).json()["documents"]
    assert [d["source_hash"] for d in remaining] == ["h_dogs"]

    # Deleting again is a no-op: nothing left to remove.
    again = client.delete("/documents/h_cats", headers=_AUTH)
    assert again.status_code == 200
    assert again.json()["deleted_chunks"] == 0


def test_document_admin_unsupported_store_degrades() -> None:
    container = replace(build_container(Settings(ingest_token=_TOKEN)), store=_AdminlessStore())
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as client:
            listing = client.get("/documents", headers=_AUTH)
            assert listing.status_code == 200
            body = listing.json()
            assert body["supported"] is False
            assert body["documents"] == []

            deletion = client.delete("/documents/anything", headers=_AUTH)
            assert deletion.status_code == 501
    finally:
        app.dependency_overrides.clear()
