"""``EvalSettings`` ↔ ``.env.example`` parity — the eval's counterpart of
``tests/contract/test_config_env_parity.py``. ``EVAL_*`` keys are documented as COMMENTED lines
(``# EVAL_X=``): the server never reads them, so they must not look like live server config.
"""

from __future__ import annotations

import re
from pathlib import Path

from sift.config import Settings
from sift.eval.config import EvalSettings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"


def test_env_example_documents_every_eval_setting() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    documented = set(re.findall(r"^# (EVAL_[A-Z0-9_]+)=", text, re.MULTILINE))
    fields = {f"EVAL_{name.upper()}" for name in EvalSettings.model_fields}

    assert documented == fields, (
        f"missing from .env.example: {sorted(fields - documented)}; "
        f"stale in .env.example: {sorted(documented - fields)}"
    )


def test_anthropic_judge_completer_sends_no_temperature() -> None:
    # The abstention check reuses the app's `recap_temperature`; Claude rejects it.
    app = Settings(ingest_token="t", recap_temperature=0.3)

    assert EvalSettings(judge_provider="anthropic").judge_settings(app).recap_temperature is None
    assert EvalSettings().judge_settings(app).recap_temperature == 0.3


def test_eval_keys_are_never_live_lines() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")

    assert not re.findall(r"^EVAL_", text, re.MULTILINE)
