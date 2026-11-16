"""Turn a run's rows into ``summary.json`` / ``summary.md`` / ``report.html``, and diff two runs.

Everything here is pure: rows in, dicts and strings out. The HTML is one self-contained file
(inline CSS, no scripts, no network) so a run folder can be zipped, attached, or opened offline.
"""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sift.eval.golden import GoldenItem
from sift.eval.judge import LOWER_IS_BETTER, METRICS
from sift.eval.matching import passage_matches
from sift.eval.metrics import chunk_scores, doc_scores, latency_stats, mean_scores
from sift.eval.noise import NoiseTrial
from sift.eval.records import SURFACES, SurfaceResult

FIND_STAGES = ("embed", "retrieve", "collapse", "rerank", "recap", "total")
ASK_STAGES = ("model", "tools", "total")


# --- summary ---------------------------------------------------------------------------------


def _metric_stats(values: Sequence[float | None]) -> dict[str, float]:
    ok = [v for v in values if v is not None and not math.isnan(v)]
    out: dict[str, float] = {"n": len(ok), "failed": len(values) - len(ok)}
    if ok:
        out["mean"] = sum(ok) / len(ok)
    return out


def _retrieval(
    rows: Sequence[SurfaceResult],
    items: Mapping[str, GoldenItem],
    ks: Sequence[int],
    threshold: float,
) -> dict[str, Any]:
    def stage(attr: str, chunk_level: bool) -> dict[str, Any]:
        out: dict[str, Any] = {
            "doc": mean_scores(
                doc_scores(getattr(r, attr), items[r.item_id].relevant, ks) for r in rows
            )
        }
        if chunk_level:
            out["chunk"] = mean_scores(
                chunk_scores(getattr(r, attr), items[r.item_id].relevant, ks, threshold)
                for r in rows
            )
        return out

    graded = [r for r in rows if items[r.item_id].relevant]
    if not graded:
        return {}
    if graded[0].surface == "find":
        return {"retrieved": stage("retrieved", True), "final": stage("ranked", True)}
    return {"cited": stage("ranked", False)}


def summarize_surface(
    rows: Sequence[SurfaceResult],
    items: Mapping[str, GoldenItem],
    ks: Sequence[int],
    threshold: float,
) -> dict[str, Any]:
    ok = [r for r in rows if not r.error]
    out: dict[str, Any] = {
        "n": len(rows),
        "errors": len(rows) - len(ok),
        "retrieval": _retrieval(ok, items, ks, threshold),
        "answer": {
            m: _metric_stats([r.scores[m] for r in ok if m in r.scores])
            for m in METRICS
            if any(m in r.scores for r in ok)
        },
    }
    abstention = {
        "correct_abstention": _metric_stats(
            [
                r.scores["abstained"]
                for r in ok
                if "abstained" in r.scores and not items[r.item_id].answerable
            ]
        ),
        "false_refusal": _metric_stats(
            [
                r.scores["abstained"]
                for r in ok
                if "abstained" in r.scores and items[r.item_id].answerable
            ]
        ),
    }
    out["abstention"] = {k: v for k, v in abstention.items() if v["n"] or v["failed"]}
    stages = FIND_STAGES if rows and rows[0].surface == "find" else ASK_STAGES
    out["latency_ms"] = {
        s: latency_stats(r.timings_ms[s] for r in ok if s in r.timings_ms)
        for s in stages
        if any(s in r.timings_ms for r in ok)
    }
    if rows and rows[0].surface == "ask":
        out["tool_calls_mean"] = sum(r.tool_calls for r in ok) / len(ok) if ok else 0.0
        out["truncated"] = sum(1 for r in ok if r.truncated)
    return out


def summarize_noise(trials: Sequence[NoiseTrial], skipped: Sequence[str]) -> dict[str, Any]:
    by_ratio: list[dict[str, Any]] = []
    for ratio in sorted({t.ratio for t in trials}):
        bucket = [t for t in trials if t.ratio == ratio and not t.error]
        row: dict[str, Any] = {
            "ratio": ratio,
            "actual_ratio": sum(t.actual_ratio for t in bucket) / len(bucket) if bucket else 0.0,
            "n": len(bucket),
        }
        for metric in ("answer_correctness", "faithfulness"):
            stats = _metric_stats([t.scores[metric] for t in bucket if metric in t.scores])
            if "mean" in stats:
                row[metric] = stats["mean"]
        by_ratio.append(row)
    out: dict[str, Any] = {"by_ratio": by_ratio, "skipped": list(skipped)}
    if by_ratio and "answer_correctness" in by_ratio[0] and "answer_correctness" in by_ratio[-1]:
        clean = by_ratio[0]["answer_correctness"]
        if clean > 0:
            out["robustness"] = by_ratio[-1]["answer_correctness"] / clean
    return out


def summarize_tags(
    rows: Sequence[SurfaceResult], items: Mapping[str, GoldenItem], threshold: float
) -> dict[str, Any]:
    tags = sorted({t for i in items.values() for t in i.tags})
    out: dict[str, Any] = {}
    for tag in tags:
        ids = {i.id for i in items.values() if tag in i.tags}
        entry: dict[str, Any] = {"n": len(ids)}
        for surface in SURFACES:
            subset = [r for r in rows if r.surface == surface and r.item_id in ids and not r.error]
            if not subset:
                continue
            hit = mean_scores(doc_scores(r.ranked, items[r.item_id].relevant, [1]) for r in subset)
            if "hit@1" in hit:
                entry[f"{surface}.doc_hit@1"] = hit["hit@1"]
            # Every judged metric, so variants of one question (keywords, scenario, translated…)
            # are compared within their own tag — answer relevancy in particular depends on how
            # the question is phrased, not only on the answer.
            for metric in METRICS:
                stats = _metric_stats([r.scores[metric] for r in subset if metric in r.scores])
                if "mean" in stats:
                    entry[f"{surface}.{metric}"] = stats["mean"]
        out[tag] = entry
    return out


def summarize(
    run: Mapping[str, Any],
    items: Sequence[GoldenItem],
    rows: Sequence[SurfaceResult],
    trials: Sequence[NoiseTrial],
    skipped: Sequence[str],
    ks: Sequence[int],
    threshold: float,
) -> dict[str, Any]:
    by_id = {i.id: i for i in items}
    surfaces = {
        s: summarize_surface([r for r in rows if r.surface == s], by_id, ks, threshold)
        for s in SURFACES
        if any(r.surface == s for r in rows)
    }
    out: dict[str, Any] = {"run": dict(run), "surfaces": surfaces}
    if trials or skipped:
        out["noise"] = summarize_noise(trials, skipped)
    tags = summarize_tags(rows, by_id, threshold)
    if tags:
        out["tags"] = tags
    return out


# --- shared formatting -----------------------------------------------------------------------


def _fmt(value: Any, ms: bool = False) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int) and not ms:
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "—"
        return f"{value:.0f}" if ms else f"{value:.3f}"
    return str(value)


def _retrieval_table(retrieval: Mapping[str, Any], ks: Sequence[int]) -> list[list[str]]:
    rows: list[list[str]] = []
    for stage, levels in retrieval.items():
        for level, scores in levels.items():
            row = [stage, level]
            for k in ks:
                row += [
                    _fmt(scores.get(f"recall@{k}")),
                    _fmt(scores.get(f"precision@{k}")),
                    _fmt(scores.get(f"complete@{k}")),
                ]
            row.append(_fmt(scores.get("mrr")))
            rows.append(row)
    return rows


def _retrieval_header(ks: Sequence[int]) -> list[str]:
    return ["stage", "level", *[x for k in ks for x in (f"R@{k}", f"P@{k}", f"C@{k}")], "MRR"]


def _answer_rows(summary: Mapping[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for name, stats in summary.get("answer", {}).items():
        arrow = "↓" if name in LOWER_IS_BETTER else "↑"
        rows.append(
            [f"{name} {arrow}", _fmt(stats.get("mean")), str(stats["n"]), str(stats["failed"])]
        )
    for name, stats in summary.get("abstention", {}).items():
        arrow = "↓" if name == "false_refusal" else "↑"
        rows.append(
            [f"{name} {arrow}", _fmt(stats.get("mean")), str(stats["n"]), str(stats["failed"])]
        )
    return rows


def _latency_rows(summary: Mapping[str, Any]) -> list[list[str]]:
    return [
        [
            stage,
            *(_fmt(stats.get(k), ms=True) for k in ("mean", "p50", "p95", "max")),
            str(stats["n"]),
        ]
        for stage, stats in summary.get("latency_ms", {}).items()
    ]


# --- markdown --------------------------------------------------------------------------------


def _md_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def render_markdown(summary: Mapping[str, Any], ks: Sequence[int]) -> str:
    run = summary["run"]
    parts = [
        f"# sift-eval — {run.get('label', '')}",
        "",
        f"{run.get('created_at', '')} · {run.get('n_items', 0)} questions · "
        f"git `{run.get('git_sha', '?')}`{' (dirty)' if run.get('git_dirty') else ''} · "
        f"judge: {run.get('judge') or 'skipped'}",
    ]
    for warning in run.get("warnings", []):
        parts.append(f"\n> ⚠️ {warning}")
    for surface, data in summary["surfaces"].items():
        parts += ["", f"## {surface.title()} ({data['n']} questions, {data['errors']} errors)"]
        if data["retrieval"]:
            parts += ["", _md_table(_retrieval_header(ks), _retrieval_table(data["retrieval"], ks))]
        answer = _answer_rows(data)
        if answer:
            parts += ["", _md_table(["metric", "mean", "n", "failed"], answer)]
        latency = _latency_rows(data)
        if latency:
            parts += ["", _md_table(["latency (ms)", "mean", "p50", "p95", "max", "n"], latency)]
    noise = summary.get("noise")
    if noise:
        parts += ["", "## Noise robustness (Find recap)"]
        rows = [
            [
                _fmt(r["ratio"]),
                _fmt(r["actual_ratio"]),
                str(r["n"]),
                _fmt(r.get("answer_correctness")),
                _fmt(r.get("faithfulness")),
            ]
            for r in noise["by_ratio"]
        ]
        parts += [
            "",
            _md_table(["noise ratio", "actual", "n", "answer_correctness", "faithfulness"], rows),
            "",
            f"robustness (correctness at max noise ÷ clean): {_fmt(noise.get('robustness'))}"
            + (
                f" · skipped (no gold located): {', '.join(noise['skipped'])}"
                if noise["skipped"]
                else ""
            ),
        ]
    tags = summary.get("tags")
    if tags:
        keys = sorted({k for entry in tags.values() for k in entry if k != "n"})
        rows = [
            [tag, str(entry["n"]), *(_fmt(entry.get(k)) for k in keys)]
            for tag, entry in tags.items()
        ]
        parts += ["", "## By tag", "", _md_table(["tag", "n", *keys], rows)]
    return "\n".join(parts) + "\n"


# --- html ------------------------------------------------------------------------------------

_CSS = """
:root { --bg:#fbfbfa; --fg:#1d1d1b; --muted:#6b6b66; --line:#e3e2de; --card:#ffffff;
  --good:#1f7a4d; --bad:#b4362b; --accent:#3d5afe; --code:#f3f2ef; }
@media (prefers-color-scheme: dark) { :root { --bg:#161615; --fg:#ecebe7; --muted:#9a9993;
  --line:#2c2c2a; --card:#1e1e1c; --good:#5cc08a; --bad:#ef7a6e; --accent:#8c9eff;
  --code:#262624; } }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
  font:14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif; }
main { max-width:1080px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:22px; margin:0 0 4px; } h2 { font-size:17px; margin:32px 0 8px; }
h3 { font-size:14px; margin:16px 0 6px; color:var(--muted); font-weight:600; }
.meta { color:var(--muted); }
.warn { border-left:3px solid var(--bad); padding:6px 10px; margin:8px 0;
  background:var(--card); }
.cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(160px, 1fr));
  gap:10px; margin:16px 0; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; }
.card b { display:block; font-size:22px; font-variant-numeric:tabular-nums; }
.card span { color:var(--muted); font-size:12px; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; background:var(--card);
  border:1px solid var(--line); border-radius:8px; font-variant-numeric:tabular-nums; }
th, td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--line);
  white-space:nowrap; }
th { color:var(--muted); font-weight:600; font-size:12px; }
details { background:var(--card); border:1px solid var(--line); border-radius:8px;
  margin:6px 0; padding:8px 12px; }
summary { cursor:pointer; } .q { font-weight:600; }
pre { white-space:pre-wrap; background:var(--code); padding:8px 10px; border-radius:6px;
  margin:6px 0; font-size:13px; }
.ok { color:var(--good); } .no { color:var(--bad); }
.tag { color:var(--accent); font-size:12px; margin-left:6px; }
ol { margin:4px 0; padding-left:22px; } li { margin:2px 0; }
"""


def _html_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>" for row in rows
    )
    table = f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    return f'<div class="scroll">{table}</div>'


def _cards(summary: Mapping[str, Any]) -> str:
    cards: list[tuple[str, str]] = []
    find = summary["surfaces"].get("find")
    if find and find["retrieval"]:
        cards.append(
            (_fmt(find["retrieval"]["final"]["doc"].get("hit@1")), "Find top-1 doc accuracy")
        )
        cards.append(
            (
                _fmt(find["retrieval"]["retrieved"]["chunk"].get("mrr")),
                "Find chunk MRR (pre-rerank)",
            )
        )
    for surface, data in summary["surfaces"].items():
        stats = data["answer"].get("answer_correctness")
        if stats and "mean" in stats:
            cards.append((_fmt(stats["mean"]), f"{surface.title()} answer correctness"))
        total = data["latency_ms"].get("total")
        if total and "p50" in total:
            cards.append((f"{total['p50']:.0f} ms", f"{surface.title()} p50 latency"))
    noise = summary.get("noise", {})
    if "robustness" in noise:
        cards.append((_fmt(noise["robustness"]), "Noise robustness"))
    return (
        '<div class="cards">'
        + "".join(
            f'<div class="card"><b>{html.escape(v)}</b><span>{html.escape(k)}</span></div>'
            for v, k in cards
        )
        + "</div>"
    )


def _passages_html(
    passages: Sequence[Any], item: GoldenItem, threshold: float, limit: int = 5
) -> str:
    if not passages:
        return '<p class="meta">none</p>'
    lis = []
    for p in passages[:limit]:
        hit = any(passage_matches(p, ref, threshold) for ref in item.relevant)
        mark = '<span class="ok">✓</span>' if hit else '<span class="no">·</span>'
        score = f" · {p.score:.3f}" if p.score is not None else ""
        text = " ".join(p.text.split())
        snippet = text[:220] + ("…" if len(text) > 220 else "")
        lis.append(
            f"<li>{mark} <code>{html.escape(p.path)}</code> p.{p.page}{score}<br>"
            f'<span class="meta">{html.escape(snippet)}</span></li>'
        )
    return "<ol>" + "".join(lis) + "</ol>"


def _question_html(item: GoldenItem, rows: Sequence[SurfaceResult], threshold: float) -> str:
    tags = "".join(f'<span class="tag">#{html.escape(t)}</span>' for t in item.tags)
    flag = "" if item.answerable else ' <span class="tag">unanswerable</span>'
    gold = (
        "<ul>"
        + "".join(
            f"<li><code>{html.escape(r.path)}</code>"
            + (f" p.{r.page}" if r.page else "")
            + (f" — “{html.escape(r.evidence)}”" if r.evidence else "")
            + "</li>"
            for r in item.relevant
        )
        + "</ul>"
        if item.relevant
        else '<p class="meta">no gold evidence</p>'
    )
    body = [f"<h3>Gold</h3>{gold}"]
    if item.reference:
        body.append(f"<h3>Reference answer</h3><pre>{html.escape(item.reference)}</pre>")
    for row in rows:
        scores = ", ".join(f"{k} {_fmt(v)}" for k, v in row.scores.items()) or "not judged"
        timing = row.timings_ms.get("total")
        body.append(
            f"<h3>{row.surface.title()} · {_fmt(timing, ms=True)} ms · {html.escape(scores)}</h3>"
        )
        if row.error:
            body.append(f'<pre class="no">{html.escape(row.error)}</pre>')
            continue
        body.append(f"<pre>{html.escape(row.response) or '(empty)'}</pre>")
        label = "final ranking" if row.surface == "find" else "cited sources"
        body.append(f'<p class="meta">{label}</p>{_passages_html(row.ranked, item, threshold)}')
    return (
        f'<details><summary><span class="q">{html.escape(item.id)}</span> — '
        f"{html.escape(item.question)}{flag}{tags}</summary>{''.join(body)}</details>"
    )


def render_html(
    summary: Mapping[str, Any],
    items: Sequence[GoldenItem],
    rows: Sequence[SurfaceResult],
    ks: Sequence[int],
    threshold: float,
) -> str:
    run = summary["run"]
    parts = [
        f"<h1>sift-eval — {html.escape(str(run.get('label', '')))}</h1>",
        f'<p class="meta">{html.escape(str(run.get("created_at", "")))} · {run.get("n_items", 0)} '
        f"questions · git {html.escape(str(run.get('git_sha', '?')))}"
        f"{' (dirty)' if run.get('git_dirty') else ''} · judge: "
        f"{html.escape(str(run.get('judge') or 'skipped'))} · golden "
        f"{html.escape(str(run.get('golden_file', '')))}</p>",
    ]
    parts += [f'<div class="warn">{html.escape(w)}</div>' for w in run.get("warnings", [])]
    parts.append(_cards(summary))
    config = run.get("config", {})
    if config:
        parts += [
            "<h2>System under test</h2>",
            _html_table(["setting", "value"], [[k, _fmt(v)] for k, v in config.items()]),
        ]
    for surface, data in summary["surfaces"].items():
        parts.append(f"<h2>{surface.title()} — {data['n']} questions, {data['errors']} errors</h2>")
        if data["retrieval"]:
            parts += [
                "<h3>Retrieval</h3>",
                _html_table(_retrieval_header(ks), _retrieval_table(data["retrieval"], ks)),
            ]
        answer = _answer_rows(data)
        if answer:
            parts += ["<h3>Answers</h3>", _html_table(["metric", "mean", "n", "failed"], answer)]
        latency = _latency_rows(data)
        if latency:
            parts += [
                "<h3>Latency (ms)</h3>",
                _html_table(["stage", "mean", "p50", "p95", "max", "n"], latency),
            ]
        if surface == "ask":
            parts.append(
                f'<p class="meta">mean tool calls {_fmt(data.get("tool_calls_mean"))} · '
                f"truncated {data.get('truncated', 0)}</p>"
            )
    noise = summary.get("noise")
    if noise:
        rows_n = [
            [
                _fmt(r["ratio"]),
                _fmt(r["actual_ratio"]),
                str(r["n"]),
                _fmt(r.get("answer_correctness")),
                _fmt(r.get("faithfulness")),
            ]
            for r in noise["by_ratio"]
        ]
        parts += [
            "<h2>Noise robustness — Find recap</h2>",
            _html_table(
                ["noise ratio", "actual", "n", "answer correctness", "faithfulness"], rows_n
            ),
            f'<p class="meta">robustness {_fmt(noise.get("robustness"))}'
            + (
                f" · skipped: {html.escape(', '.join(noise['skipped']))}"
                if noise["skipped"]
                else ""
            )
            + "</p>",
        ]
    tags = summary.get("tags")
    if tags:
        keys = sorted({k for entry in tags.values() for k in entry if k != "n"})
        parts += [
            "<h2>By tag</h2>",
            _html_table(
                ["tag", "n", *keys],
                [[t, str(e["n"]), *(_fmt(e.get(k)) for k in keys)] for t, e in tags.items()],
            ),
        ]
    parts.append("<h2>Questions</h2>")
    for item in items:
        parts.append(_question_html(item, [r for r in rows if r.item_id == item.id], threshold))
    title = html.escape(f"sift-eval {run.get('label', '')}".strip())
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title><style>{_CSS}</style></head><body><main>"
        + "".join(parts)
        + "</main></body></html>\n"
    )


# --- compare ---------------------------------------------------------------------------------

_SKIP_SUFFIXES = (".n", ".failed", ".max")


def _flatten(prefix: str, value: Any, out: dict[str, float]) -> None:
    if isinstance(value, Mapping):
        for key, inner in value.items():
            _flatten(f"{prefix}.{key}" if prefix else str(key), inner, out)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        out[prefix] = float(value)


def _lower_is_better(key: str) -> bool:
    return (
        "latency_ms" in key
        or any(m in key for m in LOWER_IS_BETTER)
        or "false_refusal" in key
        or key.endswith((".errors", ".truncated", ".tool_calls_mean"))
    )


def _flat_metrics(summary: Mapping[str, Any]) -> dict[str, float]:
    flat: dict[str, float] = {}
    for section in ("surfaces", "noise"):
        _flatten(section, summary.get(section, {}), flat)
    return flat


def compare(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    """A markdown delta table of every numeric metric both summaries share (B relative to A)."""
    flat_a, flat_b = _flat_metrics(a), _flat_metrics(b)
    rows = []
    for key in sorted(flat_a.keys() & flat_b.keys()):
        if key.endswith(_SKIP_SUFFIXES) or ".ratio" in key or ".actual_ratio" in key:
            continue
        va, vb = flat_a[key], flat_b[key]
        delta = vb - va
        if abs(delta) < 1e-9:
            mark = "·"
        else:
            better = delta < 0 if _lower_is_better(key) else delta > 0
            mark = "▲ better" if better else "▼ worse"
        ms = "latency_ms" in key
        rows.append(
            [key.removeprefix("surfaces."), _fmt(va, ms), _fmt(vb, ms), f"{delta:+.3f}", mark]
        )
    run_a, run_b = a.get("run", {}), b.get("run", {})
    label_a = run_a.get("label", "A")
    label_b = run_b.get("label", "B")
    header = ["metric", f"A: {label_a}", f"B: {label_b}", "Δ (B−A)", ""]
    warning = ""
    sha_a, sha_b = run_a.get("golden_sha256"), run_b.get("golden_sha256")
    if sha_a and sha_b and sha_a != sha_b:
        # Editing the set (new questions, trimmed references, alternative gold) moves every
        # metric on its own — a delta between two different sets says nothing about the system.
        warning = (
            f"> **Different golden sets** (A {sha_a[:12]}…, {run_a.get('n_items', '?')} items; "
            f"B {sha_b[:12]}…, {run_b.get('n_items', '?')} items). Deltas mix changes to the set "
            "with changes to the system: re-run both configurations on the same set.\n\n"
        )
    return (
        f"# sift-eval compare: {label_a} → {label_b}\n\n" + warning + _md_table(header, rows) + "\n"
    )


# --- regression gate (compare --fail-on) ------------------------------------------------------


@dataclass(frozen=True)
class GateCheck:
    """One gated metric: how far the candidate moved from the baseline, in the bad direction."""

    metric: str
    baseline: float
    candidate: float
    tolerance: float
    lower_is_better: bool

    @property
    def worse_by(self) -> float:
        delta = self.candidate - self.baseline
        return (delta if self.lower_is_better else -delta) + 0.0  # no -0.000 in the table

    @property
    def failed(self) -> bool:
        return self.worse_by > self.tolerance + 1e-9


def check_regressions(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any], limits: Mapping[str, float]
) -> list[GateCheck]:
    """Check each ``metric -> tolerance`` (as ``compare`` prints the metric) between two runs.

    A metric fails when it got worse by more than its tolerance; improvements always pass.
    Raises ``ValueError`` for a metric either summary lacks (a typo must not pass silently) and
    for runs over different golden sets, whose deltas say nothing about the system.
    """
    sha_a = baseline.get("run", {}).get("golden_sha256")
    sha_b = candidate.get("run", {}).get("golden_sha256")
    if sha_a and sha_b and sha_a != sha_b:
        raise ValueError(
            "the two runs used different golden sets: re-run the baseline on the current set"
        )
    flat_a, flat_b = _flat_metrics(baseline), _flat_metrics(candidate)
    checks = []
    for metric, tolerance in limits.items():
        key = next((k for k in (f"surfaces.{metric}", metric) if k in flat_a and k in flat_b), None)
        if key is None:
            raise ValueError(f"metric {metric!r} is not in both summaries (see the compare table)")
        checks.append(GateCheck(metric, flat_a[key], flat_b[key], tolerance, _lower_is_better(key)))
    return checks


def render_gate(checks: Sequence[GateCheck]) -> str:
    """The gate's verdict as markdown, for the terminal and a CI job summary."""
    rows = [
        [
            c.metric,
            f"{c.baseline:.3f}",
            f"{c.candidate:.3f}",
            f"{c.worse_by:+.3f}",
            f"{c.tolerance:.3f}",
            "✗ fail" if c.failed else "✓ pass",
        ]
        for c in checks
    ]
    header = ["metric", "baseline", "candidate", "worse by", "allowed", ""]
    failed = sum(c.failed for c in checks)
    verdict = (
        f"**FAILED**: {failed} of {len(checks)} metric(s) got worse beyond tolerance."
        if failed
        else f"**passed**: no gated metric got worse beyond tolerance ({len(checks)} checked)."
    )
    return "\n## Regression gate\n\n" + _md_table(header, rows) + "\n\n" + verdict + "\n"
