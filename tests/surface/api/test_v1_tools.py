"""TestClient coverage for the ``/v1/tools/*`` toolbox surface (offline, fakes only).

``POST /v1/tools/search`` (raw retrieval, no recap), ``GET /v1/tools/documents`` (paginated,
optional metadata filter), ``GET /v1/tools/documents/{hash}/chunks`` (ordered chunks), and
``GET /v1/tools/schema`` (both manifest formats) — every route is a thin renderer over
:class:`~sift.pipelines.tools.ToolRegistry` (``Container.tools``) and sits behind the same
``resolve_tenant`` bearer chokepoint as every other route. The container is the wired fakes
from :func:`~sift.factory.build_container` with real chunks seeded into the shared
``FakeVectorStore``, injected via ``app.dependency_overrides`` so no network is touched.
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

_MODIFIED_AT = "2026-02-03T04:05:06+00:00"

_SEED: tuple[tuple[str, str, int, str, dict[str, str] | None, str | None], ...] = (
    ("alpha cats one", "cats.md", 0, "h_cats", {"project": "condense"}, _MODIFIED_AT),
    ("alpha cats two", "cats.md", 1, "h_cats", {"project": "condense"}, _MODIFIED_AT),
    ("alpha dogs one", "dogs.md", 0, "h_dogs", None, None),
)


def _seeded_container() -> Container:
    settings = Settings(ingest_token=_TOKEN)
    container = build_container(settings)
    store = container.store
    embedder = FakeEmbedder(settings.embed_dim)

    async def _seed() -> None:
        await store.ensure_ready(settings.embed_model, settings.embed_dim, "default")
        for text, path, index, source_hash, metadata, modified_at in _SEED:
            chunk = Chunk(
                text=text,
                source_path=path,
                page=1,
                source_hash=source_hash,
                index=index,
                metadata=metadata,
                modified_at=modified_at,
            )
            (vector,) = await embedder.embed([chunk.text])
            await store.upsert([replace(chunk, vector=vector)], "default")

    asyncio.run(_seed())
    return container


@pytest.fixture(autouse=True)
def _ingest_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_TOKEN", _TOKEN)
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    container = _seeded_container()
    app.dependency_overrides[get_container] = lambda: container
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --- POST /v1/tools/search ------------------------------------------------------------


def test_tools_search_requires_auth(client: TestClient) -> None:
    response = client.post("/v1/tools/search", json={"query": "alpha"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_tools_search_returns_raw_hits_no_recap(client: TestClient) -> None:
    response = client.post("/v1/tools/search", json={"query": "alpha cats one"}, headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert "summary" not in body  # the toolbox primitive never recaps
    hits = body["hits"]
    assert hits
    assert hits[0]["source_path"] == "cats.md"
    assert hits[0]["text"] == "alpha cats one"


def test_tools_search_hit_includes_modified_at_and_metadata(client: TestClient) -> None:
    """D44: a search hit must carry the source file's true `modified_at` plus its `metadata` —
    the signals a time/recency question is answered from, never a filename-embedded date."""
    response = client.post("/v1/tools/search", json={"query": "alpha cats one"}, headers=_AUTH)

    assert response.status_code == 200
    (hit,) = [h for h in response.json()["hits"] if h["source_path"] == "cats.md"][:1]
    assert hit["modified_at"] == _MODIFIED_AT
    assert hit["metadata"] == {"project": "condense"}


def test_tools_search_metadata_filter(client: TestClient) -> None:
    response = client.post(
        "/v1/tools/search",
        json={"query": "alpha", "k": 10, "filters": {"metadata": {"project": "condense"}}},
        headers=_AUTH,
    )

    assert response.status_code == 200
    hits = response.json()["hits"]
    assert hits
    assert all(hit["source_path"] == "cats.md" for hit in hits)


def test_tools_search_k_is_capped(client: TestClient) -> None:
    response = client.post("/v1/tools/search", json={"query": "alpha", "k": 999}, headers=_AUTH)

    assert response.status_code == 200
    assert len(response.json()["hits"]) <= 20  # Settings.tools_search_max_k default


# --- GET /v1/tools/documents -----------------------------------------------------------


def test_tools_documents_requires_auth(client: TestClient) -> None:
    response = client.get("/v1/tools/documents")

    assert response.status_code == 401


def test_tools_documents_paginates_and_reports_total(client: TestClient) -> None:
    response = client.get("/v1/tools/documents", params={"limit": 1, "offset": 0}, headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2  # two distinct source files (cats.md, dogs.md)
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert len(body["documents"]) == 1


def test_tools_documents_item_includes_modified_at(client: TestClient) -> None:
    """D44: `GET /v1/tools/documents` items must carry `modified_at` (or `null` when the file
    was never given one at ingest)."""
    response = client.get("/v1/tools/documents", headers=_AUTH)

    assert response.status_code == 200
    by_hash = {d["source_hash"]: d for d in response.json()["documents"]}
    assert by_hash["h_cats"]["modified_at"] == _MODIFIED_AT
    assert by_hash["h_dogs"]["modified_at"] is None


def test_tools_documents_metadata_filter(client: TestClient) -> None:
    response = client.get(
        "/v1/tools/documents",
        params={"metadata": '{"project": "condense"}'},
        headers=_AUTH,
    )

    assert response.status_code == 200
    body = response.json()
    assert [d["source_hash"] for d in body["documents"]] == ["h_cats"]
    assert body["total"] == 1


def test_tools_documents_junk_metadata_param_is_ignored(client: TestClient) -> None:
    response = client.get("/v1/tools/documents", params={"metadata": "not-json"}, headers=_AUTH)

    assert response.status_code == 200
    assert response.json()["total"] == 2  # unfiltered — junk treated as "no filter"


# --- GET /v1/tools/documents/{hash}/chunks ----------------------------------------------


def test_tools_document_chunks_requires_auth(client: TestClient) -> None:
    response = client.get("/v1/tools/documents/h_cats/chunks")

    assert response.status_code == 401


def test_tools_document_chunks_returns_ordered_chunks(client: TestClient) -> None:
    response = client.get("/v1/tools/documents/h_cats/chunks", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["source_hash"] == "h_cats"
    assert [c["text"] for c in body["chunks"]] == ["alpha cats one", "alpha cats two"]
    assert [c["index"] for c in body["chunks"]] == [0, 1]


def test_tools_document_chunks_include_modified_at_and_metadata(client: TestClient) -> None:
    """D44: each chunk returned by `GET /v1/tools/documents/{hash}/chunks` must carry
    `modified_at` + `metadata`."""
    response = client.get("/v1/tools/documents/h_cats/chunks", headers=_AUTH)

    assert response.status_code == 200
    for chunk in response.json()["chunks"]:
        assert chunk["modified_at"] == _MODIFIED_AT
        assert chunk["metadata"] == {"project": "condense"}


def test_tools_document_chunks_unknown_hash_is_empty(client: TestClient) -> None:
    response = client.get("/v1/tools/documents/does-not-exist/chunks", headers=_AUTH)

    assert response.status_code == 200
    assert response.json()["chunks"] == []


# --- GET /v1/tools/schema --------------------------------------------------------------


def test_tools_schema_requires_auth(client: TestClient) -> None:
    response = client.get("/v1/tools/schema")

    assert response.status_code == 401


def test_tools_schema_returns_both_formats(client: TestClient) -> None:
    response = client.get("/v1/tools/schema", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    names = {entry["function"]["name"] for entry in body["openai_functions"]}
    assert names == {"search", "list_documents", "get_document_chunks"}
    manifest_names = {tool["name"] for tool in body["json_schema"]["tools"]}
    assert manifest_names == names


def test_tools_schema_never_contains_settings(client: TestClient) -> None:
    response = client.get("/v1/tools/schema", headers=_AUTH)

    body = response.json()
    for entry in body["openai_functions"]:
        assert entry["function"]["name"] != "settings"
    for tool in body["json_schema"]["tools"]:
        assert tool["name"] != "settings"
