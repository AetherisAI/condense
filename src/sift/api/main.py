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


def create_app() -> FastAPI:
    """Assemble the FastAPI app: the lifespan-built container plus the routes."""
    app = FastAPI(title="Condense", lifespan=lifespan)
    app.include_router(router)
    app.include_router(v1_router)
    return app


app = create_app()
