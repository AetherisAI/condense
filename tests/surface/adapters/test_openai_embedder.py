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
from sift.core.errors import EmbedInputError

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


async def test_non_429_error_is_not_retried_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-429 failure never enters the 429 backoff-retry loop (only one attempt at the
    ORIGINAL text) — it falls straight to the single-input shrink path (D73) instead, which is
    covered by its own dedicated tests below."""

    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    seen = _patch_transport(monkeypatch, server_error)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    with pytest.raises(EmbedInputError):
        await embedder.embed(["alpha"])

    # First attempt at "alpha", then exactly one shrink-and-retry attempt — no 429-style backoff
    # loop (which would have been up to `retry_attempts` requests).
    assert len(seen) == 2
    assert json.loads(seen[0].content)["input"] == ["alpha"]


# --- Poison-input isolation (DECISIONS.md D73) ---------------------------------------------

# A long-enough marker that a poison input is still recognizable by its prefix after the
# single-input shrink path's ~10% tail truncation (dropping the last few chars of a 60+-char
# string never removes this prefix) — a bare `"poison" in inputs` equality check would stop
# matching the moment the shrink attempt truncates it, making these tests flaky w.r.t. D73's
# reactive shrink retry.
_POISON = "poison-marker-input-that-stays-recognizable-after-any-single-truncation-attempt"


def _poison_or_ok(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    inputs = payload["input"]
    if any(text.startswith("poison-marker") for text in inputs):
        return httpx.Response(500, json={"error": "input too large to process"})
    return httpx.Response(200, json={"data": [{"embedding": [0.0] * DIM} for _ in inputs]})


async def test_mixed_batch_isolates_poison_input_via_bisection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A batch with one poison input among many good ones must not sacrifice the good ones: a
    500 on the whole batch triggers bisection down to exactly the poison input, order-
    independent. The good inputs are lost too in THIS call (the port still returns
    ``list[Vector]`` for a fully successful call only) — recovering them is
    ``pipelines/ingest.py``'s job, covered in ``tests/pipelines/test_ingest.py``. This test locks
    in that the poison input is correctly *identified* (by index + server message) regardless of
    where it sits in the batch."""
    seen = _patch_transport(monkeypatch, _poison_or_ok)
    texts = [f"good{i}" for i in range(9)] + [_POISON]
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", batch_size=10)

    with pytest.raises(EmbedInputError) as exc_info:
        await embedder.embed(texts)

    assert exc_info.value.index == 9
    assert "input too large to process" in exc_info.value.message
    # Bisection actually happened: more than the single initial whole-batch POST.
    assert len(seen) > 1


async def test_mixed_batch_poison_isolated_regardless_of_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same guarantee as above, poison-first instead of poison-last — order-independent."""
    _patch_transport(monkeypatch, _poison_or_ok)
    texts = [_POISON] + [f"good{i}" for i in range(9)]
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", batch_size=10)

    with pytest.raises(EmbedInputError) as exc_info:
        await embedder.embed(texts)

    assert exc_info.value.index == 0
    assert "input too large to process" in exc_info.value.message


async def test_single_input_failure_gets_shrink_retry_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A single input rejected once (e.g. too many tokens) gets exactly one truncated-tail retry;
    if the shrunk version is accepted, the caller sees a normal, successful embed — no exception,
    no signal that a retry happened beyond the logged warning."""
    long_text = "x" * 100

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        (text,) = payload["input"]
        if len(text) == 100:
            return httpx.Response(500, json={"error": "input too large to process"})
        return httpx.Response(200, json={"data": [{"embedding": [0.0] * DIM}]})

    seen = _patch_transport(monkeypatch, handler)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    out = await embedder.embed([long_text])

    assert len(out) == 1
    assert len(seen) == 2
    # The retry sent a truncated (~10% shorter) version of the same input.
    retried_text = json.loads(seen[1].content)["input"][0]
    assert len(retried_text) == 90
    assert retried_text == long_text[:90]


async def test_single_input_failure_raises_embed_input_error_with_index_and_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When even the shrunk retry fails, the caller gets a typed, per-input error carrying the
    input's index and the backend's own message — never a bare httpx status string."""
    seen = _patch_transport(
        monkeypatch, lambda request: httpx.Response(500, json={"error": "still too large"})
    )
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", batch_size=2)

    with pytest.raises(EmbedInputError) as exc_info:
        await embedder.embed(["alpha", "beta"])

    # Bisected down to size-1 batches; the left half is always awaited (and so raises) before the
    # right half is ever attempted, so this deterministically surfaces index 0 first.
    assert exc_info.value.index == 0
    assert exc_info.value.message == "still too large"
    # Whole-batch attempt + left-half single-input attempt + its one shrink retry.
    assert len(seen) == 3


async def test_429_is_never_bisected_or_shrunk(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 429 (even on a single-input batch, even past the retry budget) must never fall into the
    bisection/shrink path — it is a retryable concurrency limit, not a bad input. Regression
    guard: the 429 path's request count and exception type stay exactly what they were before
    D73 (see ``test_429_retries_are_exhausted_then_raises`` above, unchanged)."""
    seen = _patch_transport(
        monkeypatch, lambda request: httpx.Response(429, json={"error": "Model is overloaded"})
    )

    async def _fake_sleep(seconds: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", _fake_sleep)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3")

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await embedder.embed(["alpha"])

    assert exc_info.value.response.status_code == 429
    assert len(seen) == 3  # exactly the 429 retry budget — no extra shrink attempt


# --- Proactive per-input cap (D73, EMBED_MAX_INPUT_TOKENS) ----------------------------------


async def test_max_input_tokens_zero_means_no_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", max_input_tokens=0)
    long_text = "word " * 1000

    await embedder.embed([long_text])

    assert json.loads(seen[0].content)["input"] == [long_text]


async def test_max_input_tokens_truncates_oversized_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An input whose estimated token count exceeds the cap is truncated BEFORE ever being sent
    — proactive defense-in-depth alongside the reactive bisection/shrink path."""
    seen = _patch_transport(monkeypatch, _ok)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", max_input_tokens=10)
    long_text = "x" * 1000  # estimated ~500 tokens at the 2-chars/token heuristic

    out = await embedder.embed([long_text])

    assert len(out) == 1
    sent_text = json.loads(seen[0].content)["input"][0]
    assert len(sent_text) == 20  # 10 tokens * 2 chars/token
    assert sent_text == long_text[:20]


async def test_max_input_tokens_leaves_short_input_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _patch_transport(monkeypatch, _ok)
    embedder = OpenAICompatEmbedder(base_url="http://emb/v1", model="bge-m3", max_input_tokens=1000)

    await embedder.embed(["short"])

    assert json.loads(seen[0].content)["input"] == ["short"]
