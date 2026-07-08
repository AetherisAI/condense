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
import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.llm.null import NullCompleter
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.api.deps import get_container
from sift.api.main import app
from sift.api.routes import _SECRET_KEYS, _parse_modified_at
from sift.config import Settings, get_settings
from sift.core.hashing import content_hash
from sift.core.types import Chunk, Document, Page
from sift.factory import Container, build_container
from sift.pipelines.ingest import IngestOutcome, IngestPipeline
from sift.pipelines.search import SearchPipeline

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


def test_search_recap_false_returns_source_only(client: TestClient) -> None:
    response = client.get("/search", params={"q": _SEED_TEXT, "recap": "false"}, headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    # recap=false → no LLM summary, just the doc + page citation.
    assert body["summary"] == ""
    (source,) = body["sources"]
    assert source["path"] == _SEED_PATH
    assert source["page"] == 1
    assert source["snippet"] == _SEED_TEXT


def test_status_requires_auth(client: TestClient) -> None:
    assert client.get("/status").status_code == 401


def test_status_exposes_config_but_redacts_secrets(client: TestClient) -> None:
    response = client.get("/status", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    settings = body["settings"]
    # Non-secret config is visible...
    assert settings["final_k"] == 1
    assert "recap_enabled" in settings
    # ...but secret values are never serialized — only a "set"/None presence flag.
    assert settings["ingest_token"] in ("set", None)
    assert settings["ingest_token"] != _TOKEN  # never the real token value
    for secret in ("llm_api_key", "embed_api_key", "turso_auth_token"):
        assert settings[secret] in ("set", None)


def test_status_redacts_every_secret_key() -> None:
    """Regression test: GET /status must never leak the raw value of ANY key in
    ``_SECRET_KEYS`` — including ``ocr_api_key``, which was missing from the redaction set
    and came back as plaintext (docs/channel audit finding).

    Builds its own container with a real value on every secret field so a missing entry in
    ``_SECRET_KEYS`` (present or future) fails loudly instead of silently passing because the
    field happened to be unset/falsy in the shared fixture.
    """
    secret_values: dict[str, Any] = {
        "turso_auth_token": "tt-secret",
        "embed_api_key": "embed-secret",
        "llm_api_key": "llm-secret",
        "ingest_token": _TOKEN,
        "ocr_api_key": "ocr-secret",
        # Per-consumer bearer credentials — redacted like any other secret so /status can't be
        # used to harvest every consumer's plaintext token (security review, 2026-07-06).
        "auth_tokens": "consumer-a:tok-a,consumer-b:tok-b",
    }
    # Keep this fixture honest: if a new secret is added to _SECRET_KEYS without a value here
    # (or vice versa), fail the test rather than silently under-covering it.
    assert set(secret_values) == _SECRET_KEYS

    settings = Settings(**secret_values)
    container = build_container(settings)
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/status", headers=_AUTH)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()["settings"]
    for key, raw_value in secret_values.items():
        assert body[key] in ("set", None), f"{key} was not redacted: {body[key]!r}"
        assert body[key] != raw_value, f"{key} leaked its raw value"


def test_status_reports_component_health(client: TestClient) -> None:
    response = client.get("/status", headers=_AUTH)

    assert response.status_code == 200
    comps = response.json()["components"]
    assert set(comps) == {"embeddings", "llm", "reranker", "storage"}
    # The fake store is reachable; remote deps are unconfigured offline (no base URLs in tests).
    assert comps["storage"]["status"] == "ok"
    assert comps["embeddings"]["status"] == "not_configured"
    assert comps["llm"]["status"] == "not_configured"


def test_patch_settings_applies_editable_fields(client: TestClient) -> None:
    response = client.patch(
        "/settings", json={"recap_temperature": 0.9, "final_k": 2}, headers=_AUTH
    )

    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["recap_temperature"] == 0.9
    assert settings["final_k"] == 2


def test_patch_settings_rejects_non_editable_field(client: TestClient) -> None:
    # Models/secrets/urls are not on the SettingsPatch allowlist (extra="forbid") → 422.
    response = client.patch("/settings", json={"embed_model": "evil"}, headers=_AUTH)
    assert response.status_code == 422


def test_patch_settings_requires_auth(client: TestClient) -> None:
    assert client.patch("/settings", json={"final_k": 3}).status_code == 401


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
    response = client.post("/ingest", files=[("files", ("notes.txt", b"hi", "text/plain"))])

    assert response.status_code == 401


def test_parse_modified_at_drops_invalid_values(caplog: pytest.LogCaptureFixture) -> None:
    """A1 regression: the audit's exact scenario — a garbage value like 'corrupted-not-a-date'
    used to be stored verbatim and could out-rank a real ISO date under raw string comparison
    (see A2/`_is_newer`). It must be dropped at the boundary, not stored, with a WARNING naming
    the offending file — the well-formed entries in the same map are unaffected.
    """
    with caplog.at_level(logging.WARNING, logger="sift.api.routes"):
        parsed = _parse_modified_at(
            json.dumps({"good.md": "2026-01-01T00:00:00+00:00", "bad.md": "corrupted-not-a-date"})
        )

    assert parsed == {"good.md": "2026-01-01T00:00:00+00:00"}
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "bad.md" in warnings[0].getMessage()


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


def test_ingest_wires_modified_at_into_stored_chunks() -> None:
    """A6 regression: the multipart ``modified_at`` map sent to ``POST /ingest`` must reach the
    *stored* chunk's ``modified_at`` (not just survive parsing) — and a file whose value fails
    ISO-8601 validation (A1) stores ``None`` rather than the garbage string.
    """
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
    app.dependency_overrides[get_container] = lambda: container

    good_mtime = "2026-01-01T00:00:00+00:00"
    modified_at = json.dumps({"good.txt": good_mtime, "bad.txt": "corrupted-not-a-date"})

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/ingest",
                files=[
                    ("files", ("good.txt", b"alpha content", "text/plain")),
                    ("files", ("bad.txt", b"beta content", "text/plain")),
                ],
                data={"modified_at": modified_at},
                headers=_AUTH,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert {r["status"] for r in response.json()["results"]} == {"indexed"}

    async def _stored_mtime(text: str) -> str | None:
        (vector,) = await embedder.embed([text])
        (hit,) = await store.search(vector, 1, "default")
        return hit.modified_at

    assert asyncio.run(_stored_mtime("alpha content")) == good_mtime
    assert asyncio.run(_stored_mtime("beta content")) is None  # invalid value dropped, not stored


def test_manifest_returns_known_hashes(client: TestClient) -> None:
    response = client.get("/ingest/manifest", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == "default"
    assert body["hashes"] == [_SEED_HASH]


class _CannedIngest:
    """A ``SupportsIngest`` stand-in returning fixed outcomes — no real pipeline needed."""

    def __init__(self, outcomes: list[IngestOutcome]) -> None:
        self._outcomes = outcomes

    async def ingest(
        self,
        files: Sequence[tuple[str, bytes]],
        tenant: str,
        modified_at: Mapping[str, str] | None = None,
    ) -> list[IngestOutcome]:
        return self._outcomes


def test_ingest_logs_one_warning_per_failure_and_an_info_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """E3 regression: a batch that returns HTTP 200 must never silently hide a lost file — every
    failed outcome gets its own WARNING (path + detail) and the whole batch gets one INFO
    summary of indexed/skipped/failed counts."""
    outcomes = [
        IngestOutcome(path="good.md", status="indexed", content_hash="h1", chunks=2),
        IngestOutcome(path="bad.md", status="failed", detail="boom: bad bytes"),
        IngestOutcome(path="dup.md", status="skipped_dedup", content_hash="h2"),
    ]
    settings = Settings(ingest_token=_TOKEN)
    container = replace(build_container(settings), ingest=_CannedIngest(outcomes))
    app.dependency_overrides[get_container] = lambda: container

    try:
        with caplog.at_level(logging.INFO, logger="sift.api.routes"):
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/ingest",
                    files=[("files", ("bad.md", b"x", "text/plain"))],
                    headers=_AUTH,
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "bad.md" in warnings[0].getMessage()
    assert "boom: bad bytes" in warnings[0].getMessage()

    summaries = [
        r for r in caplog.records if r.levelname == "INFO" and "ingest batch" in r.getMessage()
    ]
    assert len(summaries) == 1
    summary = summaries[0].getMessage()
    assert "indexed=1" in summary
    assert "skipped_dedup=1" in summary
    assert "failed=1" in summary
    assert "total=3" in summary


async def test_healthz_stays_responsive_while_embedder_is_slow() -> None:
    """Root-cause regression guard (E2, the TEI-OOM incident): a slow/hung embed backend must
    never block the ASGI event loop — GET /healthz must stay servable while a /search sits on a
    stuck embedder. Uses an ``asyncio.Event``-gated fake (not real network I/O, not
    ``time.sleep``) so the assertion is deterministic rather than timing-dependent: if a future
    change ever made a handler block the loop synchronously, the /healthz call below would hang
    behind /search instead of returning immediately, and the ``wait_for`` would time out.
    """
    started = asyncio.Event()
    release = asyncio.Event()

    class HangingEmbedder:
        dim = 8

        async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
            started.set()
            await release.wait()
            return [tuple(0.0 for _ in range(self.dim)) for _ in texts]

    settings = Settings(ingest_token=_TOKEN)
    base = build_container(settings)
    slow_search = SearchPipeline(
        HangingEmbedder(),  # type: ignore[arg-type]
        base.store,
        NullReranker(),
        NullCompleter(),
        settings,
    )
    container = replace(base, search=slow_search)
    app.dependency_overrides[get_container] = lambda: container

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            search_task = asyncio.create_task(
                client.get("/search", params={"q": "anything"}, headers=_AUTH)
            )
            await asyncio.wait_for(started.wait(), timeout=2.0)

            # /healthz must return promptly *while* /search is still hung inside the embedder.
            healthz_response = await asyncio.wait_for(client.get("/healthz"), timeout=2.0)
            assert healthz_response.status_code == 200
            assert not search_task.done()

            release.set()
            search_response = await asyncio.wait_for(search_task, timeout=2.0)
            assert search_response.status_code == 200
    finally:
        app.dependency_overrides.clear()
