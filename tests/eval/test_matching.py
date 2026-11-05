"""Gold matching (D75): path suffixes, page narrowing, and tolerant evidence quotes."""

from __future__ import annotations

import pytest

from sift.eval.golden import GoldRef
from sift.eval.matching import evidence_matches, passage_matches, path_matches
from sift.eval.records import Passage


@pytest.mark.parametrize(
    ("candidate", "gold", "expected"),
    [
        ("policies/refunds.md", "policies/refunds.md", True),
        ("/Users/q/docs/policies/refunds.md", "policies/refunds.md", True),
        ("policies/refunds.md", "/Users/q/docs/policies/refunds.md", True),
        ("C:\\docs\\policies\\refunds.md", "policies/refunds.md", True),
        ("policies/old_refunds.md", "refunds.md", False),  # suffix must sit on a `/` boundary
        ("policies/refunds.md", "refunds_v2.md", False),
        ("", "refunds.md", False),
    ],
)
def test_path_matches(candidate: str, gold: str, expected: bool) -> None:
    assert path_matches(candidate, gold) is expected


def test_evidence_substring_ignores_case_punctuation_and_whitespace() -> None:
    text = "Refunds take TWO to three\nbusiness-days, per the policy."

    assert evidence_matches("two to three business days", text, threshold=0.6)


def test_evidence_partial_run_uses_threshold() -> None:
    # A quote straddling a chunk boundary: only its first 4 of 6 tokens land in this chunk.
    text = "lorem ipsum refunds are processed within ten"
    quote = "refunds are processed within ten business"

    assert evidence_matches(quote, text, threshold=0.6)
    assert not evidence_matches(quote, text, threshold=0.9)


def test_scattered_shared_words_are_not_a_match() -> None:
    # Every quote token appears, but never contiguously — a topical chunk, not the evidence.
    text = "days of business are three, and two of them are refund days"

    assert not evidence_matches("two to three business days", text, threshold=0.6)


def test_passage_matches_checks_path_then_page_then_evidence() -> None:
    passage = Passage(path="docs/refunds.md", page=2, text="refunds take two to three days")

    assert passage_matches(passage, GoldRef(path="refunds.md"), 0.6)
    assert passage_matches(passage, GoldRef(path="refunds.md", page=2), 0.6)
    assert not passage_matches(passage, GoldRef(path="refunds.md", page=3), 0.6)
    assert passage_matches(passage, GoldRef(path="refunds.md", evidence="two to three"), 0.6)
    assert not passage_matches(passage, GoldRef(path="refunds.md", evidence="ten weeks"), 0.6)
    assert not passage_matches(passage, GoldRef(path="other.md", evidence="two to three"), 0.6)
