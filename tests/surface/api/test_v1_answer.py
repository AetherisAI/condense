"""``TestClient`` coverage for ``POST /v1/answer`` (WP v0.2.0 T3, D40) — offline, fakes only.

Mirrors ``test_v1_tools.py``'s pattern: the wired ``Container`` from
:func:`~sift.factory.build_container`, with ``container.answer`` swapped (via
``dataclasses.replace`` — ``Container`` is frozen) for one built on a scripted
``FakeToolCompleter`` so no network/live LLM is ever touched, injected via
``app.dependency_overrides``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from sift.adapters.conversation.fake import FakeConversationStore
from sift.adapters.llm.fake import FakeToolCompleter
from sift.api.deps import get_container
from sift.api.main import app
from sift.config import Settings, get_settings
from sift.core.types import ToolCall, ToolCompletion
from sift.factory import Container, build_container
from sift.pipelines.answer import AnswerPipeline

_TOKEN = "t"
_AUTH = {"Authorization": f"Bearer {_TOKEN}"}


def _container_with_completer(completer: FakeToolCompleter) -> Container:
    settings = Settings(ingest_token=_TOKEN)
    base = build_container(settings)
    answer = AnswerPipeline(completer, base.tools, FakeConversationStore(), settings)
    return replace(base, answer=answer)


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
def enumeration_client() -> Iterator[TestClient]:
    completer = FakeToolCompleter(
        [
            ToolCompletion(tool_calls=(ToolCall(name="list_documents", arguments={}),)),
            ToolCompletion(content="Alice and Bob."),
        ]
    )
    yield from _client(_container_with_completer(completer))


def test_answer_requires_auth(enumeration_client: TestClient) -> None:
    response = enumeration_client.post("/v1/answer", json={"message": "hi"})

    assert response.status_code == 401


def test_answer_non_stream_shape(enumeration_client: TestClient) -> None:
    response = enumeration_client.post(
        "/v1/answer", json={"message": "List everyone"}, headers=_AUTH
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "answer",
        "format",
        "conversation_id",
        "trace",
        "truncated",
        "sources",
        "grounding_used",
        "from_general_knowledge",
        "grounding_segments",
    }
    assert body["answer"] == "Alice and Bob."
    assert body["format"] == "text"
    assert body["truncated"] is False
    assert body["conversation_id"]
    assert body["sources"] == []  # this scenario never calls `search`
    assert body["grounding_used"] == "strict"  # Settings.answer_grounding_default
    assert body["from_general_knowledge"] is False
    assert body["grounding_segments"] == [{"text": "Alice and Bob.", "kind": "grounded"}]
    trace_types = [event["type"] for event in body["trace"]]
    assert "answer_delta" not in trace_types  # collapsed into `answer`
    assert trace_types == ["tool_call", "tool_result", "sources", "grounding", "done"]
    assert body["trace"][0]["tool"] == "list_documents"


def test_answer_stream_emits_events_in_order(enumeration_client: TestClient) -> None:
    with enumeration_client.stream(
        "POST",
        "/v1/answer",
        json={"message": "List everyone", "stream": True},
        headers=_AUTH,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        events = [
            json.loads(line[len("data: ") :])
            for line in response.iter_lines()
            if line.startswith("data: ")
        ]

    assert [e["type"] for e in events] == [
        "tool_call",
        "tool_result",
        "answer_delta",
        "sources",
        "grounding",
        "done",
    ]
    assert events[0]["tool"] == "list_documents"
    assert events[-4]["text"] == "Alice and Bob."
    assert events[-2]["grounding_used"] == "strict"
    assert events[-2]["from_general_knowledge"] is False
    assert events[-2]["segments"] == [{"text": "Alice and Bob.", "kind": "grounded"}]
    assert events[-1]["truncated"] is False


def test_answer_stream_over_the_wire_marks_general_knowledge_hybrid(
    enumeration_client: TestClient,
) -> None:
    """BUG-2 (D48) end-to-end: over the actual HTTP SSE response, a hybrid answer that mixes
    grounded and `[General knowledge]`-marked content carries the structured segments a
    consumer (the Chat UI) can render distinctly — not just the boolean flag."""
    completer = FakeToolCompleter(
        [
            ToolCompletion(
                content="Grounded fact. [General knowledge] Salesforce and HubSpot are similar."
            )
        ]
    )
    container = _container_with_completer(completer)
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/v1/answer",
                json={"message": "hi", "stream": True, "grounding": "hybrid"},
                headers=_AUTH,
            ) as response:
                events = [
                    json.loads(line[len("data: ") :])
                    for line in response.iter_lines()
                    if line.startswith("data: ")
                ]

        assert events[-1]["type"] == "done"
        grounding = events[-2]
        assert grounding["type"] == "grounding"
        assert grounding["from_general_knowledge"] is True
        kinds = [seg["kind"] for seg in grounding["segments"]]
        assert "grounded" in kinds
        assert "general_knowledge" in kinds
    finally:
        app.dependency_overrides.clear()


def test_answer_stream_reaches_done_even_when_the_completer_raises_mid_loop(
    enumeration_client: TestClient,
) -> None:
    """BUG-1 (D48) end-to-end regression: reproduced live with a genuine provider 429 mid-loop
    that crashed the SSE stream with no terminal frame, stranding the Chat UI on "thinking..."
    forever. Over the real HTTP response, an exception from the completer must still finalize
    the stream with "grounding" -> "done" (truncated) — never a dropped/hanging connection."""

    def _boom(_messages: object) -> ToolCompletion:
        raise RuntimeError("simulated 429 Too Many Requests")

    completer = FakeToolCompleter([_boom])
    container = _container_with_completer(completer)
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as client:
            with client.stream(
                "POST",
                "/v1/answer",
                json={"message": "hi", "stream": True, "grounding": "hybrid"},
                headers=_AUTH,
            ) as response:
                assert response.status_code == 200
                events = [
                    json.loads(line[len("data: ") :])
                    for line in response.iter_lines()
                    if line.startswith("data: ")
                ]

        assert events, "the stream must never end with zero frames"
        assert events[-1]["type"] == "done"
        assert events[-1]["truncated"] is True
    finally:
        app.dependency_overrides.clear()


def test_answer_conversation_id_round_trips_across_two_calls() -> None:
    completer = FakeToolCompleter(
        [ToolCompletion(content="first answer"), ToolCompletion(content="second answer")]
    )
    container = _container_with_completer(completer)
    app.dependency_overrides[get_container] = lambda: container
    try:
        with TestClient(app) as client:
            first = client.post("/v1/answer", json={"message": "hello"}, headers=_AUTH).json()
            conversation_id = first["conversation_id"]

            second = client.post(
                "/v1/answer",
                json={"message": "follow up", "conversation_id": conversation_id},
                headers=_AUTH,
            ).json()

        assert second["conversation_id"] == conversation_id
        assert second["answer"] == "second answer"
    finally:
        app.dependency_overrides.clear()


def test_answer_json_format_field_round_trips(enumeration_client: TestClient) -> None:
    response = enumeration_client.post(
        "/v1/answer",
        json={"message": "extract", "format": "json", "json_schema": {"type": "object"}},
        headers=_AUTH,
    )

    assert response.status_code == 200
    assert response.json()["format"] == "json"


# --- grounding modes (D46) ---------------------------------------------------------------


def test_answer_grounding_defaults_to_strict_when_omitted(enumeration_client: TestClient) -> None:
    response = enumeration_client.post(
        "/v1/answer", json={"message": "List everyone"}, headers=_AUTH
    )

    assert response.status_code == 200
    assert response.json()["grounding_used"] == "strict"


def test_answer_per_request_grounding_overrides_settings_default(
    enumeration_client: TestClient,
) -> None:
    """Settings.answer_grounding_default is "strict" (the test's Settings() default) — a
    per-request "open" must win."""
    response = enumeration_client.post(
        "/v1/answer", json={"message": "List everyone", "grounding": "open"}, headers=_AUTH
    )

    assert response.status_code == 200
    assert response.json()["grounding_used"] == "open"


def test_answer_rejects_bogus_grounding_value(enumeration_client: TestClient) -> None:
    response = enumeration_client.post(
        "/v1/answer", json={"message": "hi", "grounding": "bogus"}, headers=_AUTH
    )

    assert response.status_code == 422
