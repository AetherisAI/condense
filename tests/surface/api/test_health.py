"""Tests for the ``/status`` component health probes (``sift.api.health``).

Root-cause regression: ``EMBED_BASE_URL`` points at TEI (text-embeddings-inference), an
OpenAI-compatible embeddings server that does NOT serve ``GET {base}/models`` — only
``POST {base}/embeddings`` (health/info live at TEI's own root, not under the OpenAI-style
``/v1`` base). The generic ``_probe_openai_compat`` (shared with the LLM probe) GETs
``{base}/models`` and TEI answers 404, so the embeddings component reported ``down`` even
though real embedding calls succeeded end-to-end. The embeddings probe now performs the same
minimal, real ``POST {base}/embeddings`` call the production embedder makes — the most
definitive, still-cheap proof of actual capability — routed through an ``httpx.MockTransport``
(no network), matching the style of ``tests/surface/adapters/test_openai_embedder.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from sift.adapters.store.fake import FakeVectorStore
from sift.api.health import gather_components
from sift.config import Settings


def _patch_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> list[httpx.Request]:
    """Make every ``httpx.AsyncClient`` use a MockTransport; record the requests it sends."""
    seen: list[httpx.Request] = []

    def _record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(_record)
    real_client = httpx.AsyncClient

    def _make_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _make_client)
    return seen


def _settings(*, embed_api_key: str | None = None, embed_model: str = "bge-m3") -> Settings:
    # Explicit, individually-typed kwargs (no ``**dict`` splat into ``Settings(...)``) — a splat
    # defeats pydantic-settings' generated ``__init__`` overloads and pyright reports every other
    # field as a type mismatch (the known baseline drift in ``test_routes.py``); naming each
    # field here keeps this file's pyright count at zero.
    return Settings(
        ingest_token="t",
        embed_base_url="http://emb/v1",
        embed_api_key=embed_api_key,
        embed_model=embed_model,
    )


async def test_embeddings_ok_when_tei_serves_embeddings_but_not_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact TEI shape that caused the bug: GET {base}/models -> 404, but the real
    ``POST {base}/embeddings`` call — the thing search actually depends on — succeeds."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(404, json={"error": "not found"})
        assert request.url.path == "/v1/embeddings"
        return httpx.Response(200, json={"data": [{"embedding": [0.0] * 1024}]})

    seen = _patch_transport(monkeypatch, handler)
    settings = _settings()

    comps = await gather_components(settings, FakeVectorStore(), "default")

    assert comps["embeddings"].status == "ok"
    # The probe never bothers with the GET /models path that doesn't exist on TEI.
    assert all(request.method == "POST" for request in seen)
    assert len(seen) == 1


async def test_embeddings_down_when_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_transport(monkeypatch, handler)
    settings = _settings()

    comps = await gather_components(settings, FakeVectorStore(), "default")

    assert comps["embeddings"].status == "down"
    assert comps["embeddings"].detail == "ConnectError"


async def test_embeddings_down_on_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda request: httpx.Response(500, json={"error": "boom"}))
    settings = _settings()

    comps = await gather_components(settings, FakeVectorStore(), "default")

    assert comps["embeddings"].status == "down"
    assert comps["embeddings"].detail == "HTTP 500"


async def test_embeddings_not_configured_without_base_url() -> None:
    settings = Settings(ingest_token="t")

    comps = await gather_components(settings, FakeVectorStore(), "default")

    assert comps["embeddings"].status == "not_configured"


async def test_embeddings_probe_sends_bearer_and_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.0] * 1024}]})

    seen = _patch_transport(monkeypatch, handler)
    settings = _settings(embed_api_key="secret", embed_model="bge-m3")

    comps = await gather_components(settings, FakeVectorStore(), "default")

    assert comps["embeddings"].model == "bge-m3"
    (request,) = seen
    assert request.method == "POST"
    assert request.url.path == "/v1/embeddings"
    assert request.headers["authorization"] == "Bearer secret"
