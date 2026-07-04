"""Tests for ``agent/config.py`` — the agent's own persisted settings (separate from
``sift.config.Settings``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent.config import AgentConfig, load


def test_default_timeout_is_600() -> None:
    """Matches SiftClient's new default (D36): one OCR-heavy batch exceeded the old 300s."""
    assert AgentConfig().timeout == 600.0


def test_load_tolerates_a_config_saved_before_the_timeout_field_existed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An old ``config.json`` with no ``timeout`` key must still load, defaulting the new field."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"engine_url": "http://x", "token": "t", "watch_paths": ["/a"]}))
    monkeypatch.setattr("agent.config.config_path", lambda: str(path))

    cfg = load()

    assert cfg.timeout == 600.0
    assert cfg.engine_url == "http://x"


def test_load_reads_a_persisted_custom_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"engine_url": "http://x", "token": "t", "watch_paths": ["/a"], "timeout": 45.0})
    )
    monkeypatch.setattr("agent.config.config_path", lambda: str(path))

    cfg = load()

    assert cfg.timeout == 45.0
