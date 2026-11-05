"""Eval-suite fixtures: hermetic config plus a small seeded corpus on the default fakes.

Same hermeticity rule as ``tests/surface/conftest.py`` — a developer's local ``.env`` (real
Mistral/libSQL, and now ``EVAL_*``) must never leak into these tests — extended to
:class:`~sift.eval.config.EvalSettings`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import pytest

from sift.adapters.embedding.fake import FakeEmbedder
from sift.config import Settings, get_settings
from sift.core.types import Chunk
from sift.eval.config import EvalSettings
from sift.factory import Container, build_container

TENANT = "default"
DIM = 16

# Three small documents; refunds v1/v2 mirrors the version-aware retrieval story (D28/D33).
CORPUS: tuple[tuple[str, int, str], ...] = (
    ("policies/refunds.md", 1, "refunds take two to three business days after approval"),
    ("policies/shipping.md", 1, "shipping is free for orders above fifty euros"),
    ("policies/shipping.md", 2, "express shipping arrives the next business day"),
    ("hr/holidays.md", 1, "employees receive twenty five days of paid holiday per year"),
)


@pytest.fixture(autouse=True)
def _ignore_dotenv(monkeypatch: pytest.MonkeyPatch):
    for model in (Settings, EvalSettings):
        monkeypatch.setitem(model.model_config, "env_file", None)
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    for name in EvalSettings.model_fields:
        monkeypatch.delenv(f"EVAL_{name.upper()}", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def app_settings(**overrides: object) -> Settings:
    return Settings(ingest_token="t", embed_dim=DIM, recap_context_k=2, **overrides)  # pyright: ignore[reportArgumentType]


async def seed(container: Container, corpus: Sequence[tuple[str, int, str]] = CORPUS) -> None:
    embedder = FakeEmbedder(DIM)
    await container.store.ensure_ready(container.settings.embed_model, DIM, TENANT)
    chunks = [
        Chunk(text=text, source_path=path, page=page, source_hash=f"h-{path}", index=i)
        for i, (path, page, text) in enumerate(corpus)
    ]
    vectors = await embedder.embed([c.text for c in chunks])
    await container.store.upsert(
        [replace(c, vector=v) for c, v in zip(chunks, vectors, strict=True)], TENANT
    )


@pytest.fixture
async def container() -> Container:
    built = build_container(app_settings(), ephemeral_conversations=True)
    await seed(built)
    return built
