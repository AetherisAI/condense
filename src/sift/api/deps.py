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

import hmac
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


def _match_consumer(token: str, auth_tokens: dict[str, str]) -> str | None:
    """Constant-time lookup of ``token`` in the per-consumer table (CWE-208).

    A plain ``dict.get(token)`` compares hash-then-bytes and can short-circuit; scan every
    entry with :func:`hmac.compare_digest` instead so the match time doesn't depend on which
    (or how many) leading bytes of a candidate token are correct.
    """
    matched: str | None = None
    for known_token, consumer in auth_tokens.items():
        if hmac.compare_digest(token, known_token):
            matched = consumer
    return matched


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
        # Constant-time compare (CWE-208): a plain ``==`` short-circuits at the first differing
        # byte, leaking how many leading bytes are correct via response latency. The empty
        # ``ingest_token`` default must never authenticate, so guard it explicitly.
        ingest_token = container.settings.ingest_token
        if ingest_token and hmac.compare_digest(token, ingest_token):
            logger.info("auth consumer=%r", "ingest")
            return "default"
        consumer = _match_consumer(token, container.auth_tokens)
        if consumer is not None:
            logger.info("auth consumer=%r", consumer)
            return "default"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_master(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    container: Annotated[Container, Depends(get_container)],
) -> None:
    """Gate token-management routes (``api/tokens.py``) to the master ``ingest_token`` ONLY.

    Minting/revoking per-consumer bearer tokens is a higher-privilege action than anything
    :func:`resolve_tenant` gates, so it gets its own chokepoint rather than reusing
    ``resolve_tenant`` (which would let any already-issued consumer token mint or revoke others,
    including itself). Same constant-time compare and same 401 shape as ``resolve_tenant`` for a
    missing/unrecognized token; a recognized per-consumer token is rejected 403 with a distinct,
    actionable detail rather than a bare 401 — the caller has *a* valid token, just not the
    master one.
    """
    if credentials is not None:
        token = credentials.credentials
        ingest_token = container.settings.ingest_token
        if ingest_token and hmac.compare_digest(token, ingest_token):
            return
        if _match_consumer(token, container.auth_tokens) is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="master token required",
            )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
