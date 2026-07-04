"""Surface-suite fixtures.

Keep the surface tests hermetic: a developer's local ``.env`` (used to run the app against
real Mistral/libSQL) must not leak into tests that assert on config *defaults* or build fakes.
``Settings`` reads ``.env`` via pydantic-settings, so neutralize ``env_file`` and clear the
cached singleton around every test — CI has no ``.env``, and now neither do local runs.

Nulling ``env_file`` alone isn't enough: some transitive import (e.g. ``markitdown``'s
``magika`` dependency) calls ``dotenv.load_dotenv(dotenv.find_dotenv())`` unconditionally at
*import* time, writing a local ``.env``'s real values straight into ``os.environ`` for the rest
of the process — after that, ``Settings()`` picks them up regardless of ``env_file``, because
pydantic-settings always merges real env vars. So also strip every declared ``Settings`` field's
env var explicitly (derived from ``model_fields``, not a hand-maintained list, so a newly added
field is covered automatically) before each test.
"""

from __future__ import annotations

import pytest

from sift.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _ignore_dotenv(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
