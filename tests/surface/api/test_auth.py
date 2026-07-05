"""TestClient coverage for per-consumer auth tokens (``resolve_tenant``, WP v0.2.0 T2, D38).

``Settings.auth_tokens`` ("name:token,...") is parsed once into ``Container.auth_tokens`` and
``resolve_tenant`` accepts either the legacy ``ingest_token`` or any of those named tokens, all
resolving to the same ``"default"`` tenant — an unrecognized token is still rejected 401. Uses
``GET /v1/tools/schema`` (any bearer-gated route would do) as the probe endpoint.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sift.api.deps import get_container
from sift.api.main import app
from sift.config import Settings, get_settings
from sift.factory import build_container

_INGEST_TOKEN = "ingest-secret"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_TOKEN", _INGEST_TOKEN)
    monkeypatch.delenv("AUTH_TOKENS", raising=False)
    get_settings.cache_clear()


def _client_with_auth_tokens(auth_tokens: str) -> Iterator[TestClient]:
    container = build_container(Settings(ingest_token=_INGEST_TOKEN, auth_tokens=auth_tokens))
    app.dependency_overrides[get_container] = lambda: container
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield from _client_with_auth_tokens("worktalky:wt-secret,mcp:mcp-secret")


def test_legacy_ingest_token_still_resolves(client: TestClient) -> None:
    response = client.get("/v1/tools/schema", headers={"Authorization": f"Bearer {_INGEST_TOKEN}"})

    assert response.status_code == 200


def test_named_consumer_token_resolves(client: TestClient) -> None:
    response = client.get("/v1/tools/schema", headers={"Authorization": "Bearer wt-secret"})

    assert response.status_code == 200


def test_another_named_consumer_token_resolves(client: TestClient) -> None:
    response = client.get("/v1/tools/schema", headers={"Authorization": "Bearer mcp-secret"})

    assert response.status_code == 200


def test_unknown_token_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/tools/schema", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_missing_token_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/tools/schema")

    assert response.status_code == 401


def test_no_auth_tokens_configured_only_ingest_token_works() -> None:
    for test_client in _client_with_auth_tokens(""):
        legacy = test_client.get(
            "/v1/tools/schema", headers={"Authorization": f"Bearer {_INGEST_TOKEN}"}
        )
        assert legacy.status_code == 200

        other = test_client.get(
            "/v1/tools/schema", headers={"Authorization": "Bearer anything-else"}
        )
        assert other.status_code == 401


def test_named_consumer_logged_at_info(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="sift.api.deps"):
        response = client.get("/v1/tools/schema", headers={"Authorization": "Bearer wt-secret"})

    assert response.status_code == 200
    assert "worktalky" in caplog.text
