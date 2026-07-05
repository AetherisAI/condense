"""Tests for the app's lifespan (``sift.api.main``) — BUG #1, D40 amendment.

``ensure_ready`` must run once at process startup (not just lazily inside the ``search`` tool
executor / the two toolbox executors it was just added to, ``pipelines/tools.py``) so the FIRST
request against a fresh process is never the one that discovers a not-yet-migrated store.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

import sift.api.main as main_module
from sift.adapters.store.fake import FakeVectorStore
from sift.config import Settings, get_settings
from sift.factory import Container, build_container


class _SpyStore(FakeVectorStore):
    """Records every ``ensure_ready`` call — see ``tests/pipelines/test_tools.py``'s twin."""

    def __init__(self) -> None:
        super().__init__()
        self.ensure_ready_calls: list[tuple[str, int, str]] = []

    async def ensure_ready(self, model: str, dim: int, tenant: str) -> None:
        self.ensure_ready_calls.append((model, dim, tenant))
        await super().ensure_ready(model, dim, tenant)


@pytest.fixture(autouse=True)
def _ingest_token_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("INGEST_TOKEN", "t")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_lifespan_calls_ensure_ready_once_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    spy = _SpyStore()

    def _build(settings: Settings) -> Container:
        return replace(build_container(settings), store=spy)

    monkeypatch.setattr(main_module, "build_container", _build)

    with TestClient(main_module.app):
        pass

    assert spy.ensure_ready_calls == [
        (get_settings().embed_model, get_settings().embed_dim, "default")
    ]
