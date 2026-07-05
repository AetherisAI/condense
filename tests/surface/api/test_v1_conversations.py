"""``TestClient`` coverage for ``GET``/``DELETE /v1/conversations*`` (WP v0.2.0 T6, D42) —
plain REST chat-session management, deliberately NOT ``ToolRegistry`` tools. Mirrors
``test_v1_answer.py``'s pattern: the wired ``Container`` with ``container.answer`` swapped for
one built on a scripted ``FakeToolCompleter``, injected via ``app.dependency_overrides``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from sift.adapters.conversation.fake import FakeConversationStore
from sift.adapters.llm.fake import FakeToolCompleter
from sift.api.deps import get_container
from sift.api.main import app
from sift.config import Settings, get_settings
from sift.core.types import ToolCompletion
from sift.factory import Container, build_container
from sift.pipelines.answer import AnswerPipeline

_TOKEN = "t"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


def _container_with_completer(completer: FakeToolCompleter) -> Container:
    settings = Settings(ingest_token=_TOKEN)
    base = build_container(settings)
    conversations = FakeConversationStore()
    answer = AnswerPipeline(completer, base.tools, conversations, settings)
    return replace(base, answer=answer, conversations=conversations)


@pytest.fixture(autouse=True)
def _ingest_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INGEST_TOKEN", _TOKEN)
    get_settings.cache_clear()


def _client(container: Container) -> Iterator[TestClient]:
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    completer = FakeToolCompleter([ToolCompletion(content="An answer.")])
    yield from _client(_container_with_completer(completer))


def test_list_conversations_requires_auth(client: TestClient) -> None:
    response = client.get("/v1/conversations")

    assert response.status_code == 401


def test_list_conversations_empty_before_any_answer(client: TestClient) -> None:
    response = client.get("/v1/conversations", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["conversations"] == []
    assert body["limit"] == 50
    assert body["offset"] == 0


def test_list_conversations_shows_one_after_an_answer(client: TestClient) -> None:
    answer = client.post("/v1/answer", json={"message": "hi"}, headers=_AUTH).json()

    response = client.get("/v1/conversations", headers=_AUTH)

    assert response.status_code == 200
    (conv,) = response.json()["conversations"]
    assert conv["conversation_id"] == answer["conversation_id"]
    assert conv["turn_count"] == 2  # user + assistant
    assert conv["title"] == "hi"  # NullCompleter echoes verbatim -> fallback-shaped title
    assert conv["updated_at"]


def test_list_conversations_respects_limit(client: TestClient) -> None:
    for message in ["a", "b", "c"]:
        client.post("/v1/answer", json={"message": message}, headers=_AUTH)

    response = client.get("/v1/conversations?limit=2", headers=_AUTH)

    assert len(response.json()["conversations"]) == 2


def test_get_conversation_requires_auth(client: TestClient) -> None:
    response = client.get("/v1/conversations/does-not-exist")

    assert response.status_code == 401


def test_get_conversation_returns_404_for_unknown_id(client: TestClient) -> None:
    response = client.get("/v1/conversations/does-not-exist", headers=_AUTH)

    assert response.status_code == 404


def test_get_conversation_returns_turns_incl_sources(client: TestClient) -> None:
    answer = client.post("/v1/answer", json={"message": "hi"}, headers=_AUTH).json()
    conversation_id = answer["conversation_id"]

    response = client.get(f"/v1/conversations/{conversation_id}", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == conversation_id
    assert [t["role"] for t in body["turns"]] == ["user", "assistant"]
    assert body["turns"][0]["content"] == "hi"
    assert body["turns"][1]["content"] == "An answer."
    assert body["turns"][0]["sources"] is None  # no search tool call in this scenario


def test_get_conversation_returns_turns_incl_persisted_grounding(client: TestClient) -> None:
    """D51 (BUG-B): a reopened conversation must render each assistant turn's OWN recorded
    grounding — never nulled out on reload. The user turn never carries grounding at all."""
    answer = client.post("/v1/answer", json={"message": "hi"}, headers=_AUTH).json()
    conversation_id = answer["conversation_id"]

    response = client.get(f"/v1/conversations/{conversation_id}", headers=_AUTH)

    assert response.status_code == 200
    body = response.json()
    user_turn, assistant_turn = body["turns"]
    assert user_turn["grounding_used"] is None
    assert user_turn["from_general_knowledge"] is False
    assert user_turn["grounding_segments"] == []
    assert assistant_turn["grounding_used"] == "strict"  # Settings default
    assert assistant_turn["from_general_knowledge"] is False
    assert assistant_turn["grounding_segments"] == [{"text": "An answer.", "kind": "grounded"}]


def test_delete_conversation_requires_auth(client: TestClient) -> None:
    response = client.delete("/v1/conversations/does-not-exist")

    assert response.status_code == 401


def test_delete_conversation_removes_it(client: TestClient) -> None:
    answer = client.post("/v1/answer", json={"message": "hi"}, headers=_AUTH).json()
    conversation_id = answer["conversation_id"]

    delete_response = client.delete(f"/v1/conversations/{conversation_id}", headers=_AUTH)

    assert delete_response.status_code == 200
    assert delete_response.json() == {"conversation_id": conversation_id, "deleted": True}
    assert client.get(f"/v1/conversations/{conversation_id}", headers=_AUTH).status_code == 404


def test_delete_conversation_is_idempotent(client: TestClient) -> None:
    first = client.delete("/v1/conversations/does-not-exist", headers=_AUTH)
    second = client.delete("/v1/conversations/does-not-exist", headers=_AUTH)

    assert first.status_code == 200
    assert second.status_code == 200
