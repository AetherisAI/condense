"""The "no memory vocabulary" rule, enforced mechanically (D37/D38, v0.2.0 design §0).

Condense has **documents** and **chunks** — never "memory"/"remember"/"forget". That naming
belongs to the future Brain service's interpretation layer, not to this codebase. D37 codified
the rule but deferred its mechanical enforcement to "whoever lands the toolbox/schema work in
T2" (paired with the ``PATCH /settings`` toolbox-exclusion test in ``test_tools_schema.py``) —
this is that test.

A bare ``\\bmemor(y|ies)\\b`` grep would false-positive on the *other*, entirely legitimate
sense of the word this codebase also uses — computer memory/RAM (an "in-memory" test double, a
``MemoryMax`` cgroup limit, "exhaust memory") — so known-legitimate lines are allowlisted by
their exact (stripped) text. Any NEW occurrence not on the allowlist fails this test: either it
is another legitimate RAM/systems usage (add it to the allowlist with a one-line justification)
or it is the product-vocabulary rule being broken (fix the wording instead).
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src" / "sift"
_PATTERN = re.compile(r"\bmemor(y|ies)\b", re.IGNORECASE)

# Every current hit is computer-memory (RAM/cgroup) usage, never product "memory" semantics.
_ALLOWED_LINES: frozenset[str] = frozenset(
    {
        '"""In-memory test double for the :class:`~sift.core.ports.VectorStore` port.',
        "# request — bounds memory/latency per call and stays under server batch limits.",
        '"""In-memory Embedder producing deterministic, unit-norm pseudo-embeddings."""',
        "``.xlsx`` reproduced under a ``MemoryMax=2G`` isolation scope climbed past 2GiB RSS and "
        "was",
        "attempt a parse that could exhaust memory (see DECISIONS.md D34: a stray far cell "
        "inflated",
        # WP v0.2.0 T3 (D40): both new "in-memory" hits are the same RAM sense as the two above.
        '"""In-memory test double for the ``ConversationStore`` seam (``pipelines/answer.py``, '
        "D40).",
        '"""A libSQL-backed store when a Turso database is configured, else the in-memory fake —',
    }
)


def test_no_unallowlisted_memory_vocabulary_in_src() -> None:
    offenders: dict[str, list[str]] = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if _PATTERN.search(stripped) and stripped not in _ALLOWED_LINES:
                offenders.setdefault(str(path.relative_to(SRC_DIR)), []).append(stripped)

    assert not offenders, (
        "'memory' vocabulary found outside the RAM/systems allowlist (see v0.2.0 design §0, "
        f"D37/D38): {offenders}"
    )
