"""Tests for MistralOcr — the /ocr request shape and page-joining, over a mocked transport.

No network: every ``httpx.AsyncClient`` is routed through an ``httpx.MockTransport`` so the real
request plumbing (URL, bearer header, JSON body) is exercised against a canned ``/ocr`` reply.
Asserts the document is sent as ``image_url`` for an image extension and ``document_url`` for a
PDF, that per-page ``markdown`` is joined with blank lines (dropping empties), and that a non-2xx
status propagates via ``raise_for_status``.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable

import httpx
import pytest

from sift.adapters.ocr.mistral import MistralOcr


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


def _two_pages(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "pages": [
                {"index": 0, "markdown": "# Title"},
                {"index": 1, "markdown": "body text"},
                {"index": 2, "markdown": "   "},  # blank → dropped from the join
            ]
        },
    )


async def test_image_extension_sends_image_url(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _two_pages)
    ocr = MistralOcr("https://api.mistral.ai/v1", "mistral-ocr-latest", "secret")

    text = await ocr.extract(b"\x89PNG\r\n", "shot.png")

    assert text == "# Title\n\nbody text"
    (request,) = seen
    assert str(request.url) == "https://api.mistral.ai/v1/ocr"
    assert request.headers["authorization"] == "Bearer secret"
    b64 = base64.b64encode(b"\x89PNG\r\n").decode("ascii")
    assert json.loads(request.content) == {
        "model": "mistral-ocr-latest",
        "document": {"type": "image_url", "image_url": f"data:image/png;base64,{b64}"},
    }


async def test_pdf_extension_sends_document_url(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _two_pages)
    # Trailing slash also exercises ``base_url.rstrip("/")``.
    ocr = MistralOcr("https://api.mistral.ai/v1/", "mistral-ocr-latest", "k")

    await ocr.extract(b"%PDF-1.7", "scan.pdf")

    (request,) = seen
    assert str(request.url) == "https://api.mistral.ai/v1/ocr"
    b64 = base64.b64encode(b"%PDF-1.7").decode("ascii")
    assert json.loads(request.content)["document"] == {
        "type": "document_url",
        "document_url": f"data:application/pdf;base64,{b64}",
    }


async def test_no_pages_returns_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda request: httpx.Response(200, json={"pages": []}))
    ocr = MistralOcr("https://api.mistral.ai/v1", "mistral-ocr-latest", "k")

    assert await ocr.extract(b"x", "blank.pdf") == ""


async def test_http_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda request: httpx.Response(401, json={"error": "nope"}))
    ocr = MistralOcr("https://api.mistral.ai/v1", "mistral-ocr-latest", "bad")

    with pytest.raises(httpx.HTTPStatusError):
        await ocr.extract(b"x", "a.png")


def _patch_capturing_timeout(monkeypatch: pytest.MonkeyPatch) -> dict[str, httpx.Timeout]:
    """Patch ``httpx.AsyncClient`` to record its ``timeout=`` kwarg (still answers via a
    MockTransport, so the OCR call itself succeeds)."""
    captured: dict[str, httpx.Timeout] = {}
    real_client = httpx.AsyncClient

    def _make_client(*args, **kwargs):
        timeout = kwargs.get("timeout")
        assert isinstance(timeout, httpx.Timeout)
        captured["timeout"] = timeout
        return real_client(*args, **kwargs, transport=httpx.MockTransport(_two_pages))

    monkeypatch.setattr(httpx, "AsyncClient", _make_client)
    return captured


async def test_default_timeout_is_bounded_not_a_flat_120s(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_capturing_timeout(monkeypatch)
    ocr = MistralOcr("https://api.mistral.ai/v1", "mistral-ocr-latest", "k")

    await ocr.extract(b"x", "a.png")

    timeout = captured["timeout"]
    assert timeout.connect == 5.0
    assert timeout.read == 60.0


async def test_timeouts_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_capturing_timeout(monkeypatch)
    ocr = MistralOcr(
        "https://api.mistral.ai/v1",
        "mistral-ocr-latest",
        "k",
        timeout_s=15.0,
        connect_timeout_s=3.0,
    )

    await ocr.extract(b"x", "a.png")

    timeout = captured["timeout"]
    assert timeout.connect == 3.0
    assert timeout.read == 15.0
