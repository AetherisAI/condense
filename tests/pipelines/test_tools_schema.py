"""Regression test: ``PATCH /settings`` is permanently excluded from the toolbox (D38, §2.4).

An injected prompt reaching a future tool-calling loop must be structurally unable to retune
retrieval/embedding/store settings — so ``ToolRegistry`` must never register a ``settings``
tool, and neither of its renders (``to_openai_functions``/``to_json_schema_manifest``) may
mention any :class:`~sift.api.schemas.SettingsPatch` field name. This is the standing
regression test named in the v0.2.0 design doc §3 and in D38.
"""

from __future__ import annotations

import json

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore
from sift.api.schemas import SettingsPatch
from sift.config import Settings
from sift.pipelines.tools import build_tool_registry

DIM = 16


def _registry_text() -> str:
    """Every render's JSON, concatenated — the surface a naive substring/grep check scans."""
    settings = Settings(ingest_token="t", embed_dim=DIM)
    registry = build_tool_registry(FakeEmbedder(DIM), FakeVectorStore(), settings)
    return json.dumps(registry.to_openai_functions()) + json.dumps(
        registry.to_json_schema_manifest()
    )


def test_no_settings_tool_registered() -> None:
    settings = Settings(ingest_token="t", embed_dim=DIM)
    registry = build_tool_registry(FakeEmbedder(DIM), FakeVectorStore(), settings)

    names = {tool.name for tool in registry.tools()}
    assert "settings" not in names
    assert not any("settings" in name.lower() for name in names)


def test_manifest_never_mentions_a_settings_patch_field() -> None:
    blob = _registry_text().lower()
    for field in SettingsPatch.model_fields:
        assert field.lower() not in blob, f"SettingsPatch field {field!r} leaked into the toolbox"


def test_manifest_never_mentions_settings_patch_type_name() -> None:
    blob = _registry_text().lower()
    assert "settingspatch" not in blob
    assert "patch /settings" not in blob


def test_registry_exposes_exactly_the_three_corpus_tools() -> None:
    """Chat-session management (``GET``/``DELETE /v1/conversations*``, WP v0.2.0 T6, D42) is
    plain REST over ``Container.conversations`` directly — it must NEVER become a registry
    tool, only the three deterministic corpus capabilities belong here (§0's north star)."""
    settings = Settings(ingest_token="t", embed_dim=DIM)
    registry = build_tool_registry(FakeEmbedder(DIM), FakeVectorStore(), settings)

    names = {tool.name for tool in registry.tools()}

    assert names == {"search", "list_documents", "get_document_chunks"}
