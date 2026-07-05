"""TDD coverage for engine-side CORS (``Settings.cors_origins``, D55).

The Tauri desktop shell's webview has no same-origin server to talk to — it calls an absolute,
user-configured base URL, which the browser enforces CORS against. ``Settings.cors_origins`` is
a comma-separated allow-list (default: the three ``tauri://`` origin variants a Tauri v2 webview
actually sends); an empty string disables CORS handling entirely. Browser deployments are
same-origin and never send an ``Origin`` header that differs from the server, so CORS never
triggers for them regardless of this setting — zero behavior change for the existing web UI.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sift.api.main import app
from sift.config import get_settings


@pytest.fixture(autouse=True)
def _ingest_token_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("INGEST_TOKEN", "t")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_cors_preflight_allows_tauri_origin(client: TestClient) -> None:
    r = client.options(
        "/search",
        headers={
            "Origin": "tauri://localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "tauri://localhost"
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_cors_rejects_unlisted_origin(client: TestClient) -> None:
    r = client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_disabled_when_empty(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "")
    get_settings.cache_clear()

    r = client.options(
        "/search",
        headers={
            "Origin": "tauri://localhost",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert "access-control-allow-origin" not in r.headers
