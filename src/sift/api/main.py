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
from sift.config import get_settings
from sift.factory import build_container


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the wired container once at startup and expose it on ``app.state``."""
    app.state.container = build_container(get_settings())
    yield


def create_app() -> FastAPI:
    """Assemble the FastAPI app: the lifespan-built container plus the routes."""
    app = FastAPI(title="Condense", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
