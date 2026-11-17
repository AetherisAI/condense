"""``sift-eval validate`` — does the golden set actually point at what's indexed?

Schema problems are caught by :mod:`sift.eval.golden` before this runs. Here every gold ref is
checked against the live index: its path must resolve to an ingested document (several matches
is a warning — scoring would credit any of them), and a given page or evidence quote must exist
in that document's chunks. Missing ``reference``/``relevant`` fields are warnings: the item still
runs, it just skips the metrics that need them.

Alternative groups get two extra warnings, because a loose alternative is the easy way to
inflate recall: an alternative with neither page nor evidence lets *any* chunk of that document
satisfy the whole group, and a label used by a single entry is usually a typo of another label.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from sift.config import Settings
from sift.eval.config import EvalSettings
from sift.eval.corpus import Doc, document_passages, list_documents, resolve
from sift.eval.golden import GoldenItem, GoldRef, load_golden, ref_groups
from sift.eval.matching import evidence_matches, normalize_path
from sift.eval.records import Passage
from sift.factory import Container, build_container


@dataclass(slots=True)
class ValidationReport:
    items: int = 0
    documents: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"{self.items} golden item(s) checked against {self.documents} indexed document(s)"
        ]
        lines += [f"  error:   {e}" for e in self.errors]
        lines += [f"  warning: {w}" for w in self.warnings]
        verdict = "FAILED" if self.errors else "OK"
        lines.append(f"{verdict} — {len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return "\n".join(lines)


def _suggest(path: str, docs: list[Doc]) -> str:
    names = {PurePosixPath(normalize_path(d.path)).name: d.path for d in docs}
    close = difflib.get_close_matches(PurePosixPath(normalize_path(path)).name, names, n=1)
    return f" — did you mean '{names[close[0]]}'?" if close else ""


def _check_ref(ref: GoldRef, passages: list[Passage], threshold: float) -> str | None:
    on_page = [p for p in passages if ref.page is None or p.page == ref.page]
    if ref.page is not None and not on_page:
        pages = sorted({p.page for p in passages})
        return f"page {ref.page} not found (indexed pages: {pages[:10]})"
    if ref.evidence is not None and not any(
        evidence_matches(ref.evidence, p.text, threshold) for p in on_page
    ):
        where = f" on page {ref.page}" if ref.page is not None else ""
        return f"evidence “{ref.evidence[:60]}” not found{where}"
    return None


def _group_warnings(item: GoldenItem) -> list[str]:
    warnings: list[str] = []
    for group in ref_groups(item.relevant):
        label = item.relevant[group[0]].group
        if label is None:
            continue
        if len(group) == 1:
            warnings.append(
                f"{item.id}: group '{label}' has a single entry — a typo of another label?"
            )
            continue
        for index in group:
            ref = item.relevant[index]
            if ref.page is None and ref.evidence is None:
                warnings.append(
                    f"{item.id}: alternative '{ref.path}' in group '{label}' has no page or "
                    "evidence, so any chunk of it satisfies the group — quote where it states "
                    "the answer"
                )
    return warnings


async def validate_golden(
    golden: Path, app: Settings, es: EvalSettings, container: Container | None = None
) -> ValidationReport:
    items = load_golden(golden)
    container = container or build_container(app, ephemeral_conversations=True)
    docs = await list_documents(container, es.tenant)
    report = ValidationReport(items=len(items), documents=len(docs))
    if not docs:
        report.errors.append("the index is empty — ingest documents before validating")
        return report

    chunks: dict[str, list[Passage]] = {}
    seen_questions: dict[str, str] = {}
    for item in items:
        key = " ".join(item.question.lower().split())
        if key in seen_questions:
            report.warnings.append(f"{item.id}: same question as {seen_questions[key]}")
        seen_questions.setdefault(key, item.id)
        if item.answerable and not item.relevant:
            report.warnings.append(
                f"{item.id}: no 'relevant' — retrieval metrics and the noise sweep skip it"
            )
        if item.answerable and not item.reference:
            report.warnings.append(
                f"{item.id}: no 'reference' — answer correctness and noise sweep skip it"
            )
        report.warnings += _group_warnings(item)
        for ref in item.relevant:
            matches = resolve(ref.path, docs)
            if not matches:
                report.errors.append(
                    f"{item.id}: '{ref.path}' matches no indexed document{_suggest(ref.path, docs)}"
                )
                continue
            if len(matches) > 1:
                shown = ", ".join(d.path for d in matches[:3])
                report.warnings.append(
                    f"{item.id}: '{ref.path}' matches {len(matches)} documents ({shown}) — "
                    "use a longer path to pin one"
                )
            if ref.page is None and ref.evidence is None:
                continue
            problems = []
            for doc in matches:
                if doc.source_hash not in chunks:
                    chunks[doc.source_hash] = await document_passages(
                        container, doc.source_hash, es.tenant
                    )
                problems.append(
                    _check_ref(ref, chunks[doc.source_hash], es.evidence_match_threshold)
                )
            if all(problems):
                report.errors.append(f"{item.id}: '{ref.path}' {problems[0]}")
    return report
