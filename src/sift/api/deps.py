"""API dependency seams — the Container accessor and the auth → tenant chokepoint (README §3).

Two dependencies the routes lean on. :func:`get_container` hands back the process-wide
:class:`~sift.factory.Container` the lifespan built and stashed on ``app.state`` — so handlers
get the wired pipelines without ever constructing an adapter (the dependency rule).
:func:`resolve_tenant` is the SINGLE place a bearer token becomes a tenant: the configured
``ingest_token`` OR any per-consumer token in ``Container.auth_tokens`` (WP v0.2.0 T2, D38) maps
to ``"default"``; anything else (or a missing header) is rejected 401. Multi-tenancy stays
additive — only this function changes when real tenants arrive.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sift.factory import Container

_bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def get_container(request: Request) -> Container:
    """Return the wired :class:`~sift.factory.Container` the lifespan built on ``app.state``."""
    return request.app.state.container


async def resolve_tenant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    container: Annotated[Container, Depends(get_container)],
) -> str:
    """Map the bearer token to a tenant — the one auth chokepoint (README §3).

    The configured ``ingest_token`` resolves to ``"default"`` (consumer name ``"ingest"``); so
    does any token in ``Container.auth_tokens`` (parsed from ``Settings.auth_tokens``, D38),
    each resolving to the same tenant but logged under its own consumer name for traceability —
    no behavior differs by consumer yet, this is purely observability for the multi-consumer
    future (WorkyTalky, an MCP client, ...). A missing or unrecognized token is rejected 401
    with a ``WWW-Authenticate: Bearer`` challenge.
    """
    if credentials is not None:
        token = credentials.credentials
        if token == container.settings.ingest_token:
            logger.info("auth consumer=%r", "ingest")
            return "default"
        consumer = container.auth_tokens.get(token)
        if consumer is not None:
            logger.info("auth consumer=%r", consumer)
            return "default"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
