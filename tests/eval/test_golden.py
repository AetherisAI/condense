"""Golden-set parsing: the schema `docs/evaluation.md` documents, enforced line by line."""

from __future__ import annotations

import json

import pytest

from sift.eval.golden import GoldenError, GoldRef, item_to_dict, parse_lines


def _line(**fields: object) -> str:
    return json.dumps({"id": "q1", "question": "How long do refunds take?", **fields})


def test_full_item_parses() -> None:
    (item,) = parse_lines(
        [
            _line(
                reference="Two to three business days.",
                relevant=[{"path": "refunds.md", "page": 2, "evidence": "two to three"}],
                tags=["policy"],
            )
        ]
    )

    assert item.reference == "Two to three business days."
    assert item.relevant == (GoldRef(path="refunds.md", page=2, evidence="two to three"),)
    assert item.answerable is True
    assert item.tags == ("policy",)


def test_comments_and_blank_lines_are_skipped() -> None:
    items = parse_lines(["# a comment", "", _line(), "   "])

    assert [i.id for i in items] == ["q1"]


def test_bootstrap_passthrough_keys_are_accepted() -> None:
    (item,) = parse_lines([_line(review="todo", notes="drafted from chunk 3")])

    assert item.id == "q1"


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("{not json", "invalid JSON"),
        (json.dumps(["a list"]), "must be a JSON object"),
        (json.dumps({"question": "q?"}), "'id' must be a non-empty string"),
        (_line(question=""), "'question' must be a non-empty string"),
        (_line(refrence="typo"), "unknown key(s) ['refrence']"),
        (_line(relevant=[{"file": "x.md"}]), "unknown 'relevant' key(s) ['file']"),
        (_line(relevant=[{"path": "x.md", "page": 0}]), "'page' must be an integer >= 1"),
        (_line(relevant="x.md"), "'relevant' must be a list"),
        (_line(answerable="no"), "'answerable' must be true or false"),
        (
            _line(answerable=False, relevant=[{"path": "x.md"}]),
            "an unanswerable item can't list 'relevant' evidence",
        ),
        (_line(tags="policy"), "'tags' must be a list of strings"),
    ],
)
def test_schema_violations_name_the_line(line: str, message: str) -> None:
    with pytest.raises(GoldenError) as excinfo:
        parse_lines(["# header", line], source="g.jsonl")

    assert message in str(excinfo.value)
    assert "g.jsonl:2" in str(excinfo.value)


def test_duplicate_ids_rejected() -> None:
    with pytest.raises(GoldenError, match="duplicate id 'q1'"):
        parse_lines([_line(), _line()])


def test_empty_set_rejected() -> None:
    with pytest.raises(GoldenError, match="no golden items"):
        parse_lines(["# only comments"])


def test_item_to_dict_round_trips() -> None:
    raw = json.loads(
        _line(
            reference="r",
            relevant=[{"path": "a.md", "evidence": "quote"}],
            answerable=True,
            tags=["t"],
        )
    )
    (item,) = parse_lines([json.dumps(raw)])

    assert parse_lines([json.dumps(item_to_dict(item))]) == [item]
    assert "answerable" not in item_to_dict(item)
