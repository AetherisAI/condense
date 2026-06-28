"""Surface-suite fixtures.

Keep the surface tests hermetic: a developer's local ``.env`` (used to run the app against
real Mistral/libSQL) must not leak into tests that assert on config *defaults* or build fakes.
``Settings`` reads ``.env`` via pydantic-settings, so neutralize ``env_file`` and clear the
cached singleton around every test — CI has no ``.env``, and now neither do local runs.
"""

from __future__ import annotations

import pytest

from sift.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _ignore_dotenv(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
