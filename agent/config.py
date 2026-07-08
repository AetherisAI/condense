"""Agent-local settings — persisted JSON in the per-user config dir, separate from ``sift``.

This is the agent's *own* config (engine URL, bearer token, what to watch, behaviour toggles),
nothing to do with the engine's ``sift.config.Settings``. ``platformdirs`` puts the file where
each OS expects it: ``~/Library/Application Support/sift-agent`` (macOS),
``%APPDATA%\\sift-agent`` (Windows), ``~/.config/sift-agent`` (Linux).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields

from platformdirs import user_config_dir

from agent.sync import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_FILES,
    DEFAULT_INCLUDE,
    DEFAULT_MAX_FILE_SIZE_MB,
)

_APP = "sift-agent"


def config_path() -> str:
    """Absolute path to the agent's config file (directory created on demand, mode 0700).

    The file stores the engine bearer token in cleartext, so the directory is created
    owner-only (0700) — a default umask would otherwise leave it 0755/world-traversable.
    """
    d = user_config_dir(_APP)
    os.makedirs(d, mode=0o700, exist_ok=True)
    return os.path.join(d, "config.json")


@dataclass
class AgentConfig:
    """Everything the agent needs to run, all editable from the settings dialog."""

    engine_url: str = "http://localhost:8000"
    token: str = ""
    watch_paths: list[str] = field(default_factory=list)  # one or more folders/files to index
    recursive: bool = True
    include_exts: list[str] = field(default_factory=lambda: list(DEFAULT_INCLUDE))
    delete_removed: bool = False  # remove a doc from the index when its file leaves disk
    tenant: str = "default"
    # Per-file size guard (A3): a file larger than this is skipped (never hashed/loaded) rather
    # than risk a huge scan/export ballooning the sync's memory footprint. Standalone agent, so
    # this is its own config knob — sift's Settings do not apply here.
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB
    # Directory names pruned from every walk (D35) — defaults to the built-in vendored/tooling
    # set (``.venv``, ``node_modules``, …); editable in the settings dialog to add project-
    # specific junk folders without losing the built-ins (the field starts pre-populated with them).
    exclude_dirs: list[str] = field(default_factory=lambda: sorted(DEFAULT_EXCLUDE_DIRS))
    # Filename glob patterns pruned from every walk (D39) — defaults to the built-in junk-file
    # set (``MEMORY.md``, ``CLAUDE.md``, ``*.tmp``, …); editable in the settings dialog to add
    # project-specific junk filenames without losing the built-ins (same shape as exclude_dirs).
    exclude_files: list[str] = field(default_factory=lambda: sorted(DEFAULT_EXCLUDE_FILES))
    # HTTP timeout (seconds) for every engine request. Raised from the old 300s default (D36) —
    # one real OCR-heavy batch took 5m6s server-side and the client abandoned it while the server
    # kept working. Editable in the settings dialog for a slower/heavier backend.
    timeout: float = 600.0

    @property
    def configured(self) -> bool:
        """True once there's enough to run (an engine, a token, and at least one folder)."""
        return bool(self.engine_url and self.token and self.watch_paths)

    def includes(self) -> set[str]:
        """Normalised extension set (leading dot, lowercase) for matching files."""
        out: set[str] = set()
        for e in self.include_exts:
            e = e.strip().lower()
            if e and not e.startswith("."):
                e = "." + e
            if e:
                out.add(e)
        return out


def load() -> AgentConfig:
    """Read the saved config, tolerating missing/old keys; defaults if absent."""
    path = config_path()
    if not os.path.exists(path):
        return AgentConfig()
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return AgentConfig()
    # Migrate the old single-folder key (``watch_path``) to the ``watch_paths`` list.
    if "watch_paths" not in raw and raw.get("watch_path"):
        raw["watch_paths"] = [raw["watch_path"]]
    raw.pop("watch_path", None)
    known = {f.name for f in fields(AgentConfig)}
    return AgentConfig(**{k: v for k, v in raw.items() if k in known})


def save(cfg: AgentConfig) -> None:
    """Persist ``cfg`` to the config file as pretty JSON, owner-read/write only (0600).

    The payload includes the engine bearer token, so open the file 0600 rather than let a
    default umask leave it 0644/world-readable. ``os.open`` applies the mode atomically at
    creation; an existing file is re-hardened via ``os.chmod`` in case it predates this.
    """
    path = config_path()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(asdict(cfg), fh, indent=2)
    os.chmod(path, 0o600)
