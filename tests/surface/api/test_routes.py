"""TestClient coverage for the API routes (offline, fakes only).

Drives the whole surface end-to-end through ``TestClient``: ``/healthz`` reports the pinned
embed model with no auth; ``/search`` and the ingest routes sit behind the single
``resolve_tenant`` bearer chokepoint (a missing or wrong token → 401); ``POST /ingest`` maps
each engine outcome onto the HTTP schema; ``/ingest/manifest`` returns the store's known
hashes. The container is the wired fakes from :func:`~sift.factory.build_container`, injected
via ``app.dependency_overrides`` so no network is touched.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from sift.adapters.embedding.fake import FakeEmbedder
from sift.api.deps import get_container
from sift.api.main import app
from sift.config import Settings, get_settings
from sift.core.types import Chunk
from sift.factory import Container, build_container

_TOKEN = "t"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}
_SEED_TEXT = "alpha passage about cats"
_SEED_PATH = "cats.md"
_SEED_HASH = "h1"


def _seeded_container() -> Container:
    """The default fake container (real composition root) with one chunk indexed for ``default``.

    Both fakes are deterministic, so a throwaway :class:`FakeEmbedder` produces the same vector
    the pipeline's own embedder will yield for the matching query — exact-match retrieval works.
    """
    settings = Settings(ingest_token=_TOKEN)
    container = build_container(settings)
    store = container.store

    async def _seed() -> None:
        await store.ensure_ready(settings.embed_model, settings.embed_dim, "default")
        chunk = Chunk(
            text=_SEED_TEXT,
            source_path=_SEED_PATH,
            page=1,
            source_hash=_SEED_HASH,
            index=0,
        )
        (vector,) = await FakeEmbedder(settings.embed_dim).embed([chunk.text])
        await store.upsert([replace(chunk, vector=vector)], "default")

    asyncio.run(_seed())
    return container


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


def test_healthz_reports_embed_model(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["embed_model"] == "bge-m3"


def test_search_requires_auth(client: TestClient) -> None:
    response = client.get("/search", params={"q": "anything"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_search_rejects_wrong_token(client: TestClient) -> None:
    response = client.get(
        "/search", params={"q": "anything"}, headers={"Authorization": "Bearer nope"}
    )

    assert response.status_code == 401


def test_search_returns_best_source(client: TestClient) -> None:
    response = client.get("/search", params={"q": _SEED_TEXT}, headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    # NullCompleter echoes the recap user turn (query + cited passage); FINAL_K == 1 → one citation.
    assert _SEED_TEXT in body["summary"]
    (source,) = body["sources"]
    assert source["path"] == _SEED_PATH
    assert source["page"] == 1
    assert source["score"] == pytest.approx(1.0)
    # The matched passage is surfaced so the UI can show *where* in the doc the answer is.
    assert source["snippet"] == _SEED_TEXT


def test_ingest_indexes_uploaded_file(client: TestClient) -> None:
    response = client.post(
        "/ingest",
        files=[("files", ("notes.txt", b"hello world", "text/plain"))],
        headers=_AUTH,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == "default"
    (result,) = body["results"]
    assert result["path"] == "notes.txt"
    assert result["status"] == "indexed"
    assert result["chunks"] == 1
    assert result["content_hash"] is not None


def test_ingest_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/ingest", files=[("files", ("notes.txt", b"hi", "text/plain"))]
    )

    assert response.status_code == 401


def test_manifest_returns_known_hashes(client: TestClient) -> None:
    response = client.get("/ingest/manifest", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == "default"
    assert body["hashes"] == [_SEED_HASH]
