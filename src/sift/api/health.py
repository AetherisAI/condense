"""Lightweight dependency health probes for the ``/status`` debug panel.

An ops concern, not core logic: each probe is best-effort with a short timeout and runs
concurrently. A configured-but-unreachable dependency reports ``down``; an unconfigured one
(a fake/null adapter is in use) reports ``not_configured``. No probe ever raises — failures
become a ``down`` status with the exception name as the detail.
"""

from __future__ import annotations

import asyncio

import httpx

from sift.api.schemas import ComponentHealth
from sift.config import Settings
from sift.core.ports import VectorStore

_TIMEOUT = httpx.Timeout(4.0)


async def _probe_openai_compat(
    base_url: str, api_key: str | None, model: str | None
) -> ComponentHealth:
    """GET ``{base_url}/models`` — the cheap OpenAI-compatible liveness check."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/models", headers=headers)
        if resp.is_success:
            return ComponentHealth(status="ok", model=model)
        return ComponentHealth(status="down", model=model, detail=f"HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001 — a probe must never raise
        return ComponentHealth(status="down", model=model, detail=type(exc).__name__)


async def _probe_embeddings(settings: Settings) -> ComponentHealth:
    """A single-token ``POST {base}/embeddings`` — the actual capability search depends on.

    Unlike the LLM backend, the embed backend is commonly TEI (text-embeddings-inference),
    which does NOT serve ``GET {base}/models`` under its OpenAI-compat base — only
    ``POST {base}/embeddings`` (its own liveness lives at root ``/health``/``/info``, not under
    ``/v1``). Reusing ``_probe_openai_compat`` there 404'd even though embedding calls worked
    perfectly. A minimal real embed call is definitive and still cheap, and reuses the same
    config-driven timeout phases as the production embedder (``embed_connect_timeout_s`` bounds
    the handshake, ``embed_timeout_s`` the rest) rather than the other probes' fixed 4s.
    """
    base_url = settings.embed_base_url
    assert base_url is not None  # only called once the caller has checked this
    headers = (
        {"Authorization": f"Bearer {settings.embed_api_key}"} if settings.embed_api_key else {}
    )
    timeout = httpx.Timeout(settings.embed_timeout_s, connect=settings.embed_connect_timeout_s)
    payload = {"model": settings.embed_model, "input": ["ok"]}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/embeddings", json=payload, headers=headers
            )
        if resp.is_success:
            return ComponentHealth(status="ok", model=settings.embed_model)
        return ComponentHealth(
            status="down", model=settings.embed_model, detail=f"HTTP {resp.status_code}"
        )
    except Exception as exc:  # noqa: BLE001 — a probe must never raise
        return ComponentHealth(status="down", model=settings.embed_model, detail=type(exc).__name__)


async def _probe_tei(base_url: str, model: str | None) -> ComponentHealth:
    """TEI cross-encoder exposes a ``/health`` endpoint."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{base_url.rstrip('/')}/health")
        status = "ok" if resp.is_success else "down"
        return ComponentHealth(status=status, model=model)
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(status="down", model=model, detail=type(exc).__name__)


async def _probe_store(store: VectorStore, tenant: str) -> ComponentHealth:
    """A trivial read proves the libSQL/engine store is reachable."""
    try:
        await store.known_hashes(tenant)
        return ComponentHealth(status="ok")
    except Exception as exc:  # noqa: BLE001
        return ComponentHealth(status="down", detail=type(exc).__name__)


async def gather_components(
    settings: Settings, store: VectorStore, tenant: str
) -> dict[str, ComponentHealth]:
    """Probe every configured dependency concurrently; unconfigured ones short-circuit."""

    async def embeddings() -> ComponentHealth:
        if not settings.embed_base_url:
            return ComponentHealth(status="not_configured", model=settings.embed_model)
        return await _probe_embeddings(settings)

    async def llm() -> ComponentHealth:
        if not settings.llm_base_url:
            return ComponentHealth(status="not_configured", model=settings.llm_model)
        return await _probe_openai_compat(
            settings.llm_base_url, settings.llm_api_key, settings.llm_model
        )

    async def reranker() -> ComponentHealth:
        match settings.rerank_strategy:
            case "none":
                return ComponentHealth(status="not_configured", detail="disabled")
            case "llm":
                return ComponentHealth(status="ok", detail="uses llm", model=settings.llm_model)
            case _:  # crossencoder
                if not settings.rerank_base_url:
                    return ComponentHealth(status="down", detail="no RERANK_BASE_URL")
                return await _probe_tei(settings.rerank_base_url, settings.rerank_model)

    async def storage() -> ComponentHealth:
        return await _probe_store(store, tenant)

    keys = ("embeddings", "llm", "reranker", "storage")
    results = await asyncio.gather(embeddings(), llm(), reranker(), storage())
    return dict(zip(keys, results, strict=True))
