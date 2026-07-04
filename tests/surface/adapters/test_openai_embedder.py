"""Tests for OpenAICompatEmbedder — async HTTP embedding over a mocked transport.

No network: every ``httpx.AsyncClient`` is routed through an ``httpx.MockTransport`` so the
real request/response plumbing (headers, JSON, ``raise_for_status``) is exercised against a
canned ``/embeddings`` reply.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from sift.adapters.embedding.openai_compat import OpenAICompatEmbedder

DIM = 1024


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


def _ok(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    return httpx.Response(
        200, json={"data": [{"embedding": [0.0] * DIM} for _ in payload["input"]]}
    )


async def test_embed_returns_tuples_of_configured_dim(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", api_key="secret")

    out = await embedder.embed(["alpha", "beta"])

    assert len(out) == 2
    assert all(isinstance(vec, tuple) for vec in out)
    assert all(len(vec) == DIM for vec in out)

    (request,) = seen
    assert str(request.url) == "http://emb/v1/embeddings"
    assert json.loads(request.content) == {"model": "bge-m3", "input": ["alpha", "beta"]}
    assert request.headers["authorization"] == "Bearer secret"


async def test_wrong_length_embedding_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def short(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.0] * 5}]})

    _patch_transport(monkeypatch, short)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    with pytest.raises(ValueError):
        await embedder.embed(["alpha"])


async def test_no_api_key_omits_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    await embedder.embed(["x"])

    (request,) = seen
    assert "authorization" not in request.headers


async def test_default_batch_size_is_64(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    await embedder.embed([f"t{i}" for i in range(65)])

    # 65 inputs at the default batch size of 64 → two requests, 64 then 1.
    assert len(seen) == 2
    assert len(json.loads(seen[0].content)["input"]) == 64
    assert len(json.loads(seen[1].content)["input"]) == 1


async def test_batch_size_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", batch_size=2)

    out = await embedder.embed(["a", "b", "c", "d", "e"])

    assert len(out) == 5
    # 5 inputs at batch_size=2 → three requests: 2, 2, 1.
    assert [len(json.loads(r.content)["input"]) for r in seen] == [2, 2, 1]


def _patch_capturing_timeout(monkeypatch: pytest.MonkeyPatch) -> dict[str, httpx.Timeout]:
    """Patch ``httpx.AsyncClient`` to record its ``timeout=`` kwarg (still answers via a
    MockTransport, so the embed call itself succeeds)."""
    captured: dict[str, httpx.Timeout] = {}
    real_client = httpx.AsyncClient

    def _make_client(*args, **kwargs):
        timeout = kwargs.get("timeout")
        assert isinstance(timeout, httpx.Timeout)
        captured["timeout"] = timeout
        return real_client(*args, **kwargs, transport=httpx.MockTransport(_ok))

    monkeypatch.setattr(httpx, "AsyncClient", _make_client)
    return captured


async def test_timeout_defaults_are_bounded_not_a_flat_120s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for the E2E TEI-OOM incident: a dead backend must fail fast on connect
    rather than sharing one flat 120s timeout across every phase."""
    captured = _patch_capturing_timeout(monkeypatch)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    await embedder.embed(["x"])

    timeout = captured["timeout"]
    assert timeout.connect == 5.0
    assert timeout.read == 60.0


async def test_timeouts_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_capturing_timeout(monkeypatch)
    embedder = OpenAICompatEmbedder(
        base_url="http://emb/v1", model="bge-m3", timeout_s=30.0, connect_timeout_s=2.0
    )

    await embedder.embed(["x"])

    timeout = captured["timeout"]
    assert timeout.connect == 2.0
    assert timeout.read == 30.0


async def test_429_is_retried_with_bounded_backoff_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TEI (D30) hands out one concurrency permit per input string and 429s a request that
    exceeds its free permits — retryable, not a real failure. Two 429s then a 200 must succeed
    without the caller ever seeing an exception."""
    responses = iter(
        [
            httpx.Response(429, json={"error": "Model is overloaded"}),
            httpx.Response(429, json={"error": "Model is overloaded"}),
            _ok,
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        resp = next(responses)
        return resp(request) if callable(resp) else resp

    seen = _patch_transport(monkeypatch, handler)
    sleeps: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    out = await embedder.embed(["alpha"])

    assert len(out) == 1
    assert len(seen) == 3  # 2 failed attempts + 1 success
    assert sleeps == [0.5, 2.0]


async def test_429_retries_are_exhausted_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A backend stuck at 429 past the retry budget must still surface as a real failure."""

    def always_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "Model is overloaded"})

    seen = _patch_transport(monkeypatch, always_429)

    async def _fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    with pytest.raises(httpx.HTTPStatusError):
        await embedder.embed(["alpha"])

    assert len(seen) == 3  # default embed_retry_attempts=3, no retry left after the 3rd


async def test_retry_attempts_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    def always_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "Model is overloaded"})

    seen = _patch_transport(monkeypatch, always_429)

    async def _fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", retry_attempts=1)

    with pytest.raises(httpx.HTTPStatusError):
        await embedder.embed(["alpha"])

    assert len(seen) == 1


async def test_non_429_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    seen = _patch_transport(monkeypatch, server_error)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    with pytest.raises(httpx.HTTPStatusError):
        await embedder.embed(["alpha"])

    assert len(seen) == 1  # no retry on a non-429 failure
