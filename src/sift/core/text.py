"""Word-level text helpers shared by the keyword index and query analysis (stdlib only).

The keyword index drops these stopwords from a query before matching, and retrieval uses the
same list to tell a keyword-style query ("T1553 tactic") from a question in English. English
only: the list is a refinement, and other languages work without it.
"""

from __future__ import annotations

import re

STOPWORDS: frozenset[str] = frozenset(
    "a about an and any are as at be by can could did do does for from has have how i in into "
    "is it its of on or some than that the their them then there these they this those to was "
    "were what when where which who whom whose why will with would you your".split()
)

_WORD = re.compile(r"\w+")


def words(text: str) -> list[str]:
    """``text``'s words, lowercased, in order (runs of letters, digits and underscores)."""
    return _WORD.findall(text.lower())
