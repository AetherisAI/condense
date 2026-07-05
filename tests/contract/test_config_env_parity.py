"""Config-parity guard (CLAUDE.md §8, D40 amendment): every :class:`~sift.config.Settings`
field's env key must appear in BOTH ``.env.example`` and ``docker-compose.yml``'s ``api``
service ``environment:`` block.

``.env.example`` was kept current WP-by-WP, but ``docker-compose.yml`` accumulated a real gap —
``EMBED_BATCH_SIZE``/``EMBED_TIMEOUT_S``/.../``RECAP_*``/``OCR_*``/``VERSION_COLLAPSE_*`` etc.
were configurable via ``.env`` but silently ignored by ``docker compose up`` (a container
recreate would fall back to code defaults, not whatever an operator set). A grep-based test
mechanically enforces full parity going forward instead of relying on every future field being
remembered to be added to both files by hand.
"""

from __future__ import annotations

import re
from pathlib import Path

from sift.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]

# Env keys that are legitimately compose/env-file-only (never a `Settings` field): compose's own
# host-port/bind knobs and the HF model-id passthrough for the optional `tei` profile service.
_NON_SETTINGS_KEYS = frozenset({"API_BIND", "API_PORT", "WEB_PORT", "TEI_PORT", "RERANK_HF_MODEL"})


def _settings_env_keys() -> set[str]:
    return {name.upper() for name in Settings.model_fields}


def _env_example_keys() -> set[str]:
    text = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, re.MULTILINE))


def _compose_api_env_keys() -> set[str]:
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # The `api` service's `environment:` block runs from that heading to the next top-level
    # (2-space-indented) key (`ports:`) — a small, deliberately simple slice rather than a full
    # YAML parse (no new dependency for one test).
    block = text.split("environment:\n", 1)[1].split("\n    ports:\n", 1)[0]
    return set(re.findall(r"^\s+([A-Z][A-Z0-9_]*):", block, re.MULTILINE))


def test_env_example_covers_every_settings_field() -> None:
    missing = _settings_env_keys() - _env_example_keys()
    assert not missing, f".env.example is missing Settings field(s): {sorted(missing)}"


def test_docker_compose_api_env_covers_every_settings_field() -> None:
    missing = _settings_env_keys() - _compose_api_env_keys()
    assert not missing, f"docker-compose.yml api environment is missing: {sorted(missing)}"


def test_docker_compose_api_env_has_no_stray_non_settings_keys() -> None:
    stray = _compose_api_env_keys() - _settings_env_keys() - _NON_SETTINGS_KEYS
    assert not stray, f"docker-compose.yml api environment has unexpected key(s): {sorted(stray)}"
