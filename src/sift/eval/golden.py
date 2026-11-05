"""The golden question set — JSONL schema, parsing, and structural checks (D75).

One JSON object per line::

    {"id": "refunds-01", "question": "How long do refunds take?",
     "reference": "Two to three business days.",
     "relevant": [{"path": "policies/refunds_v2.md", "page": 1,
                   "evidence": "two to three business days"}],
     "answerable": true, "tags": ["policy"]}

Blank lines and lines starting with ``#`` are skipped so a hand-written set can carry comments.
Unknown keys are an error (a typo like ``"refrence"`` would otherwise silently drop the reference
answer), except the free-form ``notes``/``review`` keys ``bootstrap`` writes for curation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_ITEM_KEYS = frozenset({"id", "question", "reference", "relevant", "answerable", "tags"})
_PASSTHROUGH_KEYS = frozenset({"notes", "review"})
_REF_KEYS = frozenset({"path", "page", "evidence"})


class GoldenError(ValueError):
    """A golden-set line that doesn't follow the schema (message names the line)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class GoldRef:
    """One piece of gold evidence: a document, optionally narrowed to a page and a quote."""

    path: str
    page: int | None = None
    evidence: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class GoldenItem:
    id: str
    question: str
    reference: str | None = None
    relevant: tuple[GoldRef, ...] = ()
    answerable: bool = True
    tags: tuple[str, ...] = ()


def _require_str(raw: Mapping[str, Any], key: str, where: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GoldenError(f"{where}: '{key}' must be a non-empty string")
    return value.strip()


def _parse_ref(raw: Any, where: str) -> GoldRef:
    if not isinstance(raw, Mapping):
        raise GoldenError(f"{where}: each 'relevant' entry must be an object")
    unknown = set(raw) - _REF_KEYS
    if unknown:
        raise GoldenError(f"{where}: unknown 'relevant' key(s) {sorted(unknown)}")
    path = _require_str(raw, "path", where)
    page = raw.get("page")
    if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
        raise GoldenError(f"{where}: 'page' must be an integer >= 1")
    evidence = raw.get("evidence")
    if evidence is not None:
        evidence = _require_str(raw, "evidence", where)
    return GoldRef(path=path, page=page, evidence=evidence)


def parse_item(raw: Any, *, where: str = "item") -> GoldenItem:
    """One golden item from its decoded JSON object, or :class:`GoldenError`."""
    if not isinstance(raw, Mapping):
        raise GoldenError(f"{where}: each line must be a JSON object")
    unknown = set(raw) - _ITEM_KEYS - _PASSTHROUGH_KEYS
    if unknown:
        raise GoldenError(
            f"{where}: unknown key(s) {sorted(unknown)} (allowed: {sorted(_ITEM_KEYS)})"
        )
    item_id = _require_str(raw, "id", where)
    where = f"{where} ({item_id})"
    question = _require_str(raw, "question", where)
    reference = raw.get("reference")
    if reference is not None:
        reference = _require_str(raw, "reference", where)
    relevant_raw = raw.get("relevant", [])
    if not isinstance(relevant_raw, list):
        raise GoldenError(f"{where}: 'relevant' must be a list")
    relevant = tuple(_parse_ref(ref, where) for ref in relevant_raw)
    answerable = raw.get("answerable", True)
    if not isinstance(answerable, bool):
        raise GoldenError(f"{where}: 'answerable' must be true or false")
    if not answerable and relevant:
        raise GoldenError(f"{where}: an unanswerable item can't list 'relevant' evidence")
    tags_raw = raw.get("tags", [])
    if not isinstance(tags_raw, list) or not all(isinstance(t, str) for t in tags_raw):
        raise GoldenError(f"{where}: 'tags' must be a list of strings")
    return GoldenItem(
        id=item_id,
        question=question,
        reference=reference,
        relevant=relevant,
        answerable=answerable,
        tags=tuple(tags_raw),
    )


def parse_lines(lines: Sequence[str], *, source: str = "golden") -> list[GoldenItem]:
    """Parse JSONL ``lines``; every structural problem raises with its line number."""
    items: list[GoldenItem] = []
    seen: set[str] = set()
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        where = f"{source}:{number}"
        try:
            raw = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise GoldenError(f"{where}: invalid JSON ({exc.msg})") from exc
        item = parse_item(raw, where=where)
        if item.id in seen:
            raise GoldenError(f"{where}: duplicate id '{item.id}'")
        seen.add(item.id)
        items.append(item)
    if not items:
        raise GoldenError(f"{source}: no golden items found")
    return items


def load_golden(path: Path) -> list[GoldenItem]:
    return parse_lines(path.read_text(encoding="utf-8").splitlines(), source=path.name)


def item_to_dict(item: GoldenItem) -> dict[str, Any]:
    """The JSONL shape of ``item`` (``None``/default fields omitted, so output stays tidy)."""
    out: dict[str, Any] = {"id": item.id, "question": item.question}
    if item.reference is not None:
        out["reference"] = item.reference
    if item.relevant:
        out["relevant"] = [
            {k: v for k, v in (("path", r.path), ("page", r.page), ("evidence", r.evidence)) if v}
            for r in item.relevant
        ]
    if not item.answerable:
        out["answerable"] = False
    if item.tags:
        out["tags"] = list(item.tags)
    return out
