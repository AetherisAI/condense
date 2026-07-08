"""TestClient coverage for ``/v1/tokens`` — mint/list/revoke per-consumer bearer tokens.

Master-only (``require_master``): a per-consumer token is rejected 403, no token 401, only the
configured ``ingest_token`` may manage tokens. A minted token authenticates immediately against
a normal bearer-gated route (``GET /status``) with no restart; a revoked one stops working
immediately. ``GET /v1/tokens`` never returns values, only names. ``env_line`` round-trips
through :func:`~sift.config.parse_auth_tokens`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from sift.api.deps import get_container
from sift.api.main import app
from sift.config import Settings, get_settings, parse_auth_tokens
from sift.factory import build_container

_INGEST_TOKEN = "ingest-secret"
_MASTER_AUTH = {"Authorization": f"Bearer {_INGEST_TOKEN}"}


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
    yield from _client_with_auth_tokens("worktalky:wt-secret")


# --- master-only enforcement -------------------------------------------------------------


def test_consumer_token_is_forbidden(client: TestClient) -> None:
    response = client.get("/v1/tokens", headers={"Authorization": "Bearer wt-secret"})

    assert response.status_code == 403
    assert "master" in response.json()["detail"].lower()


def test_missing_token_is_unauthorized(client: TestClient) -> None:
    response = client.get("/v1/tokens")

    assert response.status_code == 401


def test_unknown_token_is_unauthorized(client: TestClient) -> None:
    response = client.get("/v1/tokens", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_master_token_is_authorized(client: TestClient) -> None:
    response = client.get("/v1/tokens", headers=_MASTER_AUTH)

    assert response.status_code == 200


# --- list ---------------------------------------------------------------------------------


def test_list_shows_names_never_values(client: TestClient) -> None:
    response = client.get("/v1/tokens", headers=_MASTER_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body == {"tokens": [{"name": "worktalky"}]}
    assert "wt-secret" not in response.text


def test_list_sorted_by_name() -> None:
    for test_client in _client_with_auth_tokens("zeta:z-secret,alpha:a-secret"):
        response = test_client.get("/v1/tokens", headers=_MASTER_AUTH)
        assert [t["name"] for t in response.json()["tokens"]] == ["alpha", "zeta"]


# --- generate -----------------------------------------------------------------------------


def test_generate_new_token_authenticates_immediately(client: TestClient) -> None:
    create = client.post("/v1/tokens", json={"name": "newconsumer"}, headers=_MASTER_AUTH)

    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "newconsumer"
    new_token = body["token"]
    assert new_token

    probe = client.get("/v1/tools/schema", headers={"Authorization": f"Bearer {new_token}"})
    assert probe.status_code == 200


def test_generate_env_line_round_trips(client: TestClient) -> None:
    create = client.post("/v1/tokens", json={"name": "newconsumer"}, headers=_MASTER_AUTH)

    env_line = create.json()["env_line"]
    assert env_line.startswith("AUTH_TOKENS=")
    _, _, value = env_line.partition("=")
    parsed = parse_auth_tokens(value)
    assert parsed == {"wt-secret": "worktalky", create.json()["token"]: "newconsumer"}


def test_generate_rejects_empty_name(client: TestClient) -> None:
    response = client.post("/v1/tokens", json={"name": ""}, headers=_MASTER_AUTH)

    assert response.status_code == 422


@pytest.mark.parametrize("bad_name", ["has:colon", "has,comma", "has space", "tab\tchar"])
def test_generate_rejects_invalid_characters(client: TestClient, bad_name: str) -> None:
    response = client.post("/v1/tokens", json={"name": bad_name}, headers=_MASTER_AUTH)

    assert response.status_code == 422


def test_generate_rejects_duplicate_name(client: TestClient) -> None:
    response = client.post("/v1/tokens", json={"name": "worktalky"}, headers=_MASTER_AUTH)

    assert response.status_code == 409


def test_generate_requires_master(client: TestClient) -> None:
    response = client.post(
        "/v1/tokens",
        json={"name": "newconsumer"},
        headers={"Authorization": "Bearer wt-secret"},
    )

    assert response.status_code == 403


# --- revoke -------------------------------------------------------------------------------


def test_revoke_stops_token_working(client: TestClient) -> None:
    probe_before = client.get("/v1/tools/schema", headers={"Authorization": "Bearer wt-secret"})
    assert probe_before.status_code == 200

    revoke = client.delete("/v1/tokens/worktalky", headers=_MASTER_AUTH)
    assert revoke.status_code == 200
    assert revoke.json()["env_line"] == "AUTH_TOKENS="

    probe_after = client.get("/v1/tools/schema", headers={"Authorization": "Bearer wt-secret"})
    assert probe_after.status_code == 401


def test_revoke_unknown_name_is_404(client: TestClient) -> None:
    response = client.delete("/v1/tokens/nope", headers=_MASTER_AUTH)

    assert response.status_code == 404


def test_revoke_requires_master(client: TestClient) -> None:
    response = client.delete("/v1/tokens/worktalky", headers={"Authorization": "Bearer wt-secret"})

    assert response.status_code == 403
