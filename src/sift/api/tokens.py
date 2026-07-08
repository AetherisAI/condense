"""``/v1/tokens`` — mint/list/revoke per-consumer bearer tokens (README §3, master-gated).

Every route here sits behind :func:`~sift.api.deps.require_master` — ONLY the master
``INGEST_TOKEN`` may manage tokens, never a per-consumer one (a consumer minting its own
siblings, or revoking others, would be a privilege escalation). This is a separate chokepoint
from :func:`~sift.api.deps.resolve_tenant`, which every other route uses.

Persistence model (deliberate — read before "fixing" this): tokens minted here are
**runtime-live only**. ``POST``/``DELETE`` mutate ``Container.auth_tokens`` — the SAME
``{token: name}`` dict :func:`~sift.api.deps.resolve_tenant` scans on every request — in place,
so a newly-generated token authenticates immediately and a revoked one stops working
immediately, with no restart. The server never writes to disk or touches ``.env`` itself: this
process may not even own its env file (a container, a managed host, a dev's shell export), and
silently rewriting it out from under the operator is worse than not persisting at all. Instead
every mutating response carries ``env_line`` — the complete, current ``AUTH_TOKENS=...`` string
— and it is the OPERATOR's job to paste it into ``.env`` (or wherever ``Settings`` reads env
from) for the token to survive a restart. A restart with no persisted line reverts to whatever
``AUTH_TOKENS`` was configured at boot. The proper long-term fix — a hashed token store in
libSQL, surviving restarts without a manual copy-paste step — is deferred (tracked as a
follow-up); this runtime-only design ships the workflow (generate/revoke from the UI) today
without taking on that store-schema work.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from sift.api.deps import get_container, require_master
from sift.api.schemas import (
    TokenCreateRequest,
    TokenCreateResponse,
    TokenInfo,
    TokenListResponse,
    TokenRevokeResponse,
)
from sift.factory import Container

router = APIRouter(prefix="/v1/tokens", tags=["tokens"], dependencies=[Depends(require_master)])


def _env_line(auth_tokens: dict[str, str]) -> str:
    """Render the live ``{token: name}`` map as a complete ``AUTH_TOKENS=name:token,...`` line.

    Sorted by consumer name so the line is stable/deterministic across calls (easier to diff
    when an operator pastes successive versions into ``.env``), not because order matters to
    :func:`~sift.config.parse_auth_tokens`.
    """
    pairs = sorted((name, token) for token, name in auth_tokens.items())
    return "AUTH_TOKENS=" + ",".join(f"{name}:{token}" for name, token in pairs)


@router.get("")
async def list_tokens(
    container: Annotated[Container, Depends(get_container)],
) -> TokenListResponse:
    """Names of every live per-consumer token, sorted — values are NEVER returned here."""
    names = sorted(container.auth_tokens.values())
    return TokenListResponse(tokens=[TokenInfo(name=name) for name in names])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_token(
    body: TokenCreateRequest,
    container: Annotated[Container, Depends(get_container)],
) -> TokenCreateResponse:
    """Mint a new per-consumer token and register it LIVE in ``Container.auth_tokens``.

    Rejects a name already in use (409) — ``TokenCreateRequest`` already rejects an empty name
    or one containing ``":"``/``","``/whitespace (422). The generated token authenticates
    immediately: no restart, no separate "activate" step.
    """
    if body.name in container.auth_tokens.values():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"token name {body.name!r} already exists",
        )
    token = secrets.token_urlsafe(32)
    container.auth_tokens[token] = body.name
    return TokenCreateResponse(
        name=body.name, token=token, env_line=_env_line(container.auth_tokens)
    )


@router.delete("/{name}")
async def revoke_token(
    name: str,
    container: Annotated[Container, Depends(get_container)],
) -> TokenRevokeResponse:
    """Revoke the named consumer's token — removed from ``Container.auth_tokens`` immediately."""
    stale = [tok for tok, consumer in container.auth_tokens.items() if consumer == name]
    if not stale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"unknown token name {name!r}"
        )
    for tok in stale:
        del container.auth_tokens[tok]
    return TokenRevokeResponse(env_line=_env_line(container.auth_tokens))
