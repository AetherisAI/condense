"""Does a retrieved passage count as gold?

A passage matches a :class:`~sift.eval.golden.GoldRef` when:

1. its path matches — equal after separator normalization, or one is a ``/``-bounded suffix of
   the other (the agent may send absolute or folder-relative paths; gold is usually relative);
2. the page matches, when the gold names one;
3. the evidence quote appears in the passage, when the gold names one — as a normalized
   substring, else as a contiguous run covering at least ``threshold`` of the quote's tokens
   (tolerates a quote that straddles a chunk boundary or differs in punctuation).

Checks run cheapest-first, so the token-run comparison only ever sees passages from the gold
document itself.
"""

from __future__ import annotations

import re
import unicodedata

from sift.eval.golden import GoldRef
from sift.eval.records import Passage

_NON_WORD = re.compile(r"[^\w]+")


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().rstrip("/")


def path_matches(candidate: str, gold: str) -> bool:
    a, b = normalize_path(candidate), normalize_path(gold)
    if not a or not b:
        return False
    return a == b or a.endswith("/" + b.lstrip("/")) or b.endswith("/" + a.lstrip("/"))


def tokens(text: str) -> list[str]:
    """Lowercased word tokens, accents and punctuation folded away."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return [t for t in _NON_WORD.split(folded) if t]


def _longest_common_run(needle: list[str], haystack: list[str]) -> int:
    """Length of the longest contiguous token run shared by both sequences (DP, O(n·m))."""
    best = 0
    previous = [0] * (len(needle) + 1)
    for token in haystack:
        current = [0] * (len(needle) + 1)
        for j, wanted in enumerate(needle, start=1):
            if token == wanted:
                current[j] = previous[j - 1] + 1
                if current[j] > best:
                    best = current[j]
        previous = current
    return best


def evidence_matches(evidence: str, text: str, threshold: float) -> bool:
    quote = tokens(evidence)
    if not quote:
        return True
    body = tokens(text)
    if f" {' '.join(quote)} " in f" {' '.join(body)} ":
        return True
    return _longest_common_run(quote, body) / len(quote) >= threshold


def passage_matches(passage: Passage, ref: GoldRef, threshold: float) -> bool:
    if not path_matches(passage.path, ref.path):
        return False
    if ref.page is not None and passage.page != ref.page:
        return False
    if ref.evidence is not None and not evidence_matches(ref.evidence, passage.text, threshold):
        return False
    return True
