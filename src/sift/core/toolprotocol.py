"""The prompted-mode tool protocol's wire shape, shared by the layer that PRODUCES it
(``adapters/llm/openai_compat.py``'s ``parse_prompted_response``) and, historically, the layer
that guarded the user-facing answer against it leaking (``pipelines/answer.py``).

stdlib only (the dependency rule: ``core`` imports nothing external) -- kept here rather than
inline in the adapter because the wire shape (what counts as a control object) is conceptually
shared vocabulary, not adapter-private detail, even though the 2026-08-18 postmortem's
follow-up redesign moved the actual leak-prevention decision from a post-hoc text-shape guard
in ``pipelines/answer.py`` (deleted -- see that module's docstring) to provenance: the parser
now TAGS a reply it cannot confidently classify (``ToolCompletion.malformed``) instead of the
pipeline re-sniffing already-settled text. ``scan_protocol_objects`` is the parser's primary
tool for finding control objects anywhere in a reply; ``TRUNCATED_PROTOCOL_RE`` is its
last-resort signal for a control object that never finished parsing at all.

D73 (2026-08-18 live-demo postmortem, FAILURE A): a prompted-mode model asked a two-part
question naturally wants to call ``search`` twice in one turn, but had no legal way to say that
in a single ``{"tool": ...}`` object. The observed failure was TWO tool-call objects, one per
line, which a single ``json.loads`` could not parse (``JSONDecodeError: Extra data``); the reply
fell through to the "unstructured, treat as the final answer" branch and the raw protocol JSON
was rendered to the user as the assistant's answer, mid-demo.
"""

from __future__ import annotations

import json
import re
from typing import Any

# A control object the model began but never closed (observed: a reply cut off mid-``args``).
# scan_protocol_objects cannot see it because it never parses, but half a control message is no
# more presentable to a user than a whole one, so the parser treats it as protocol too (see
# ``parse_prompted_response``'s malformed-detection branch).
#
# Key-order and quote-style agnostic (2026-08-18 postmortem follow-up audit, D2/D3): the first
# version anchored ``\{\s*"(?:tool|final)"\s*:`` -- the opening brace IMMEDIATELY followed by
# the key -- which missed two real shapes: a truncated object whose ``args`` key happens to
# come first (``{"args": {...}, "tool": "sea``, D2) and a single-quoted Python-dict-style
# object (``{'tool': 'search', ...}``, D3). ``.{0,200}?`` (bounded, lazy, DOTALL so it can cross
# an embedded newline) lets ANY other key -- including a nested object with its own braces --
# sit between the opening brace and the ``tool``/``final`` key; ``["']`` accepts either quote
# style. The 200-char cap keeps a single ``re.search`` over one reply bounded (this is a
# best-effort shape signal, not a parser) and stops it from reaching across two genuinely
# separate objects and false-triggering on unrelated text far apart.
TRUNCATED_PROTOCOL_RE = re.compile(r'\{.{0,200}?["\'](?:tool|final)["\']\s*:', re.DOTALL)

# D5 (2026-08-18 postmortem follow-up audit): scan_protocol_objects retries a raw_decode
# attempt at EVERY unmatched ``{`` it finds, and a malformed run-on input (e.g. ``'{"a":' *
# 8000``, no closing braces anywhere) makes every attempt fail only after re-parsing most of
# what's left of the text -- quadratic in the input length, measured at ~1.5s blocking the
# event loop for a 40KB adversarial input. Two independent caps bound the worst case: no more
# than this many raw_decode ATTEMPTS total (each attempt is O(remaining length), so capping the
# attempt count caps the total work at attempts x length rather than length^2), and no more
# than this many characters of the input are considered at all. Past either cap, the scan stops
# and returns whatever it already found -- a partial result on a pathological/adversarial input
# is far better than a multi-second stall, and a real prompted-mode reply (at most a handful of
# control objects, plus whatever prose surrounds them) never comes remotely close to either
# limit. 64 was picked empirically: measured at ~33ms against the 40KB adversarial input above
# (comfortable margin under the 50ms regression-test ceiling), versus ~130ms uncapped.
# Budget is charged in CHARACTERS RE-PARSED by failed decodes, not in attempts (postmortem
# follow-up audit, second pass): a template brace in prose (``{placeholder}``) fails after one
# character, an unclosed nesting fails only after re-scanning everything left, and counting
# both as "one attempt" meant the cap had to be tiny to bound the adversary, which then starved
# a real control object sitting after a few dozen harmless braces. ``JSONDecodeError.pos`` says
# exactly how far each failed decode got, so charge that; a RecursionError (no position) is
# charged as the whole remainder. 512 KiB of re-parse work is ~13 full failures on a 40 KB
# adversarial input (measured well under 50 ms) and effectively unlimited for real prose.
_MAX_SCAN_WORK_CHARS = 512 * 1024
_MAX_SCAN_ATTEMPTS = 4096  # backstop only; the work budget is what bounds the adversary
_MAX_SCAN_CHARS = 65536  # 64 KiB


def scan_protocol_objects(text: str, *, with_spans: bool = False) -> list[Any]:
    """Return every control object (``{"tool": ...}`` / ``{"final": ...}``) found ANYWHERE in
    ``text``, in order, ignoring whatever prose sits before, between or after them.

    The first fix for D73 scanned only for values separated by whitespace ALONE, which still
    leaked the moment the model added a word of its own. Both of these were reproduced against
    the real parser and both reached the user as raw JSON::

        {"tool": ...}\\nand also\\n{"tool": ...}
        {"tool": ...}\\n{"tool": ...}\\nI will combine these.

    So anchor on the braces rather than on the whitespace between them: walk each ``{``, try
    :meth:`json.JSONDecoder.raw_decode` there, keep what parses and looks like a control object,
    and step over prose one character at a time. ``raw_decode`` (rather than ``str.split``) keeps
    values containing embedded newlines intact; starting from every ``{`` means a nested object
    is consumed by its parent's decode instead of being counted twice; and advancing past a
    failed decode means a malformed leading fragment cannot hide well-formed calls after it.

    ``with_spans=True`` returns ``(obj, (start, end))`` pairs instead of bare dicts, so a
    caller can tell how much of the reply is NOT the object (the prompted parser uses this to
    decide whether a ``{"final": ...}`` is the reply or is quoted inside a real answer).

    Bounded (D5 -- see ``_MAX_SCAN_ATTEMPTS``/``_MAX_SCAN_CHARS``): only the first
    ``_MAX_SCAN_CHARS`` of ``text`` are scanned, and no more than ``_MAX_SCAN_ATTEMPTS`` FAILED
    ``raw_decode`` attempts are made before giving up and returning whatever was already found.
    Successful decodes are not counted (postmortem follow-up audit): counting them meant that
    64 template braces in an ordinary answer -- ``{placeholder}`` in prose, LaTeX, JSON
    examples -- made a real control object after them invisible, and the genuine answer was
    then discarded as malformed. Only failures cost anything quadratic, so only failures count.
    Also catches ``RecursionError`` alongside ``json.JSONDecodeError`` (D4): a sufficiently deep
    adversarial nesting (e.g. ``'{"a":[' * 5000``, each ``:`` value itself opening a new
    object/array with no comma to close it) makes ``raw_decode`` recurse past Python's stack
    limit rather than failing cleanly with a decode error, and an uncaught ``RecursionError``
    here used to escape all the way out of the SSE stream with no terminal "done" frame.
    """
    decoder = json.JSONDecoder()
    found: list[Any] = []
    idx = 0
    length = min(len(text), _MAX_SCAN_CHARS)
    failed = 0
    work = 0
    while idx < length:
        brace = text.find("{", idx, length)
        if brace == -1:
            break
        try:
            value, end = decoder.raw_decode(text, brace)
        except json.JSONDecodeError as exc:
            failed += 1
            work += max(1, exc.pos - brace)
            if failed >= _MAX_SCAN_ATTEMPTS or work >= _MAX_SCAN_WORK_CHARS:
                break
            idx = brace + 1
            continue
        except RecursionError:
            failed += 1
            work += length - brace
            if failed >= _MAX_SCAN_ATTEMPTS or work >= _MAX_SCAN_WORK_CHARS:
                break
            idx = brace + 1
            continue
        if isinstance(value, dict) and ("tool" in value or "final" in value):
            found.append((value, (brace, end)) if with_spans else value)
        idx = max(end, brace + 1)
    return found
