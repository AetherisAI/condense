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

from agent.sync import DEFAULT_INCLUDE

_APP = "sift-agent"


def config_path() -> str:
    """Absolute path to the agent's config file (directory created on demand)."""
    d = user_config_dir(_APP)
    os.makedirs(d, exist_ok=True)
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
    """Persist ``cfg`` to the config file as pretty JSON."""
    with open(config_path(), "w", encoding="utf-8") as fh:
        json.dump(asdict(cfg), fh, indent=2)
