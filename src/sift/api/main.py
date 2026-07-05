"""The FastAPI application and its lifespan — the process entry point (README §3).

A single async lifespan runs the composition root ONCE: it builds the
:class:`~sift.factory.Container` from the cached :class:`~sift.config.Settings` and stashes it on
``app.state`` for the request-scoped :func:`~sift.api.deps.get_container` to hand to the routes.
Adapters are constructed here and nowhere else; the handlers only compose ports.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from sift.api.routes import router
from sift.api.v1 import router as v1_router
from sift.config import get_settings
from sift.factory import build_container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the wired container once at startup and expose it on ``app.state``.

    Also runs the store's ``ensure_ready`` migration/pin check right here (BUG #1, D40
    amendment) — belt-and-braces alongside the identical call each toolbox executor now makes
    (``pipelines/tools.py``): the very FIRST request against a fresh process (e.g.
    ``GET /v1/tools/documents``) must never be the one that discovers a not-yet-migrated store.
    ``"default"`` is the PoC's single hardcoded tenant (CLAUDE.md §3).
    """
    settings = get_settings()
    container = build_container(settings)
    await container.store.ensure_ready(settings.embed_model, settings.embed_dim, "default")
    app.state.container = container
    yield


class _SettingsDrivenCORSMiddleware:
    """Applies :class:`CORSMiddleware` per ``Settings.cors_origins`` (D55), resolved fresh on
    every request rather than once at app-construction time.

    Deciding the allowed origins normally means reading ``Settings`` when the middleware is
    *registered* — but that happens at import time for the module-level ``app`` singleton below,
    before ``INGEST_TOKEN`` (a required field with no default — "fails fast at startup" by
    design, see ``config.py``) is necessarily available: real startup and every test both supply
    it later, via the environment or a fixture, not before import. Resolving ``get_settings()``
    per request instead defers that read to first use (same lazy pattern ``lifespan`` already
    uses) and, as a bonus, lets tests flip ``CORS_ORIGINS`` per-test like every other setting.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
        if not origins:
            await self._app(scope, receive, send)
            return
        cors = CORSMiddleware(
            self._app, allow_origins=origins, allow_methods=["*"], allow_headers=["*"]
        )
        await cors(scope, receive, send)


def create_app() -> FastAPI:
    """Assemble the FastAPI app: the lifespan-built container plus the routes."""
    app = FastAPI(title="Condense", lifespan=lifespan)
    app.add_middleware(_SettingsDrivenCORSMiddleware)
    app.include_router(router)
    app.include_router(v1_router)
    return app


app = create_app()
