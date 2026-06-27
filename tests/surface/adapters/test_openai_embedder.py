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
