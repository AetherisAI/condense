"""``sift-eval validate`` against the seeded fake corpus."""

from __future__ import annotations

import json
from pathlib import Path

from sift.eval.config import EvalSettings
from sift.eval.validate import validate_golden
from sift.factory import Container, build_container

from .conftest import app_settings


def _golden(tmp_path: Path, *items: dict[str, object]) -> Path:
    path = tmp_path / "golden.jsonl"
    path.write_text("\n".join(json.dumps(i) for i in items) + "\n")
    return path


def _item(item_id: str, **fields: object) -> dict[str, object]:
    return {"id": item_id, "question": f"question {item_id}?", "reference": "r", **fields}


async def test_clean_set_passes(container: Container, tmp_path: Path) -> None:
    golden = _golden(
        tmp_path,
        _item("a", relevant=[{"path": "refunds.md", "evidence": "two to three business days"}]),
        _item("b", relevant=[{"path": "policies/shipping.md", "page": 2}]),
        {"id": "c", "question": "unanswerable?", "answerable": False},
    )

    report = await validate_golden(golden, container.settings, EvalSettings(), container)

    assert report.errors == [] and report.warnings == []
    assert report.render().endswith("OK — 0 error(s), 0 warning(s)")


async def test_problems_are_reported(container: Container, tmp_path: Path) -> None:
    golden = _golden(
        tmp_path,
        _item("missing", relevant=[{"path": "refund.md"}]),
        _item("page", relevant=[{"path": "shipping.md", "page": 9}]),
        _item("quote", relevant=[{"path": "refunds.md", "evidence": "thirty days"}]),
        {"id": "bare", "question": "question missing?"},
    )

    report = await validate_golden(golden, container.settings, EvalSettings(), container)

    assert report.errors == [
        "missing: 'refund.md' matches no indexed document — did you mean 'policies/refunds.md'?",
        "page: 'shipping.md' page 9 not found (indexed pages: [1, 2])",
        "quote: 'refunds.md' evidence “thirty days” not found",
    ]
    assert report.warnings == [
        "bare: same question as missing",
        "bare: no 'relevant' — retrieval metrics and the noise sweep skip it",
        "bare: no 'reference' — answer correctness and noise sweep skip it",
    ]
    assert "FAILED — 3 error(s), 3 warning(s)" in report.render()


async def test_ambiguous_path_warns(tmp_path: Path) -> None:
    from .conftest import seed

    container = build_container(app_settings(), ephemeral_conversations=True)
    await seed(container, [("a/notes.md", 1, "alpha"), ("b/notes.md", 1, "beta")])
    golden = _golden(tmp_path, _item("x", relevant=[{"path": "notes.md"}]))

    report = await validate_golden(golden, container.settings, EvalSettings(), container)

    assert report.errors == []
    assert report.warnings == [
        "x: 'notes.md' matches 2 documents (a/notes.md, b/notes.md) — use a longer path to pin one"
    ]


async def test_empty_index_is_an_error(tmp_path: Path) -> None:
    container = build_container(app_settings(), ephemeral_conversations=True)
    golden = _golden(tmp_path, _item("a"))

    report = await validate_golden(golden, container.settings, EvalSettings(), container)

    assert report.errors == ["the index is empty — ingest documents before validating"]
