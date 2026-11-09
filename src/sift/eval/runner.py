"""Orchestrates a run end to end and owns the run-folder layout.

A run folder (``<EVAL_OUTPUT_DIR>/<UTC>-<label>/``) is self-contained so ``judge`` and
``compare`` never need the original inputs::

    config.json     run metadata + the redacted Settings/EvalSettings it ran under
    golden.jsonl    a copy of the golden set as it was at run time
    results.jsonl   one SurfaceResult per (question, surface)
    noise.jsonl     one NoiseTrial per (question, noise ratio) — only with --noise
    summary.json    aggregated metrics (what ``compare`` diffs)
    summary.md      the same, as markdown tables
    report.html     self-contained HTML report with a per-question drill-down
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from sift.config import Settings
from sift.eval.collect import Progress, collect
from sift.eval.config import EvalSettings
from sift.eval.golden import GoldenItem, load_golden
from sift.eval.judge import AbstentionCheck, Judge, judge_results
from sift.eval.noise import NoiseTrial, judge_trials, run_noise_sweep
from sift.eval.records import Passage, Surface, SurfaceResult, record_from_dict
from sift.eval.report import render_html, render_markdown, summarize
from sift.factory import Container, build_completer, build_container

# Field-name suffixes that hold credentials — matched by pattern, not a list, so a future
# `*_api_key` on either settings model is redacted without anyone remembering to add it here.
_SECRET_FIELD = re.compile(r"(api_key|auth_tokens?|ingest_token|secret|password)$")
_CONFIG_KEYS = (
    "embed_model",
    "embed_dim",
    "retrieve_k",
    "final_k",
    "rerank_strategy",
    "rerank_model",
    "recap_enabled",
    "recap_context_k",
    "version_collapse_enabled",
    "chunk_size",
    "chunk_overlap",
    "chunk_tokenizer",
    "llm_model",
    "answer_tool_mode",
    "answer_max_tool_calls",
)


def redact(values: dict[str, Any]) -> dict[str, Any]:
    return {
        k: (("set" if v else None) if _SECRET_FIELD.search(k) else v) for k, v in values.items()
    }


def _git() -> tuple[str, bool]:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False
    return sha, dirty


def _ragas_version() -> str | None:
    try:
        return metadata.version("ragas")
    except metadata.PackageNotFoundError:
        return None


def _slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-") or "run"


def build_judges(app: Settings, es: EvalSettings) -> tuple[Judge, AbstentionCheck]:
    """The RAGAS judge + the abstention check, both pointed at the judge LLM (D74)."""
    from sift.eval.ragas_judge import RagasJudge

    judge_app = es.judge_settings(app)
    embed_url, embed_model, embed_key = es.judge_embed(app)
    judge = RagasJudge(
        base_url=judge_app.llm_base_url or "",
        model=judge_app.llm_model or "",
        api_key=judge_app.llm_api_key or "",
        embed_base_url=embed_url,
        embed_model=embed_model,
        embed_api_key=embed_key,
        provider=es.judge_provider,
    )
    return judge, AbstentionCheck(build_completer(judge_app))


def _run_metadata(
    label: str,
    golden: Path,
    items: Sequence[GoldenItem],
    surfaces: Sequence[Surface],
    app: Settings,
    es: EvalSettings,
    judge_name: str | None,
) -> dict[str, Any]:
    sha, dirty = _git()
    warnings: list[str] = []
    judge_model = es.judge_model_name(app)
    if judge_name and judge_model and judge_model == app.llm_model:
        warnings.append(
            f"The judge model ({judge_model}) is also the generator — models tend to grade "
            "their own answers generously. Set EVAL_JUDGE_MODEL to a different, stronger model."
        )
    dumped = app.model_dump()
    return {
        "label": label,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "git_sha": sha,
        "git_dirty": dirty,
        "golden_file": str(golden),
        "golden_sha256": hashlib.sha256(golden.read_bytes()).hexdigest(),
        "n_items": len(items),
        "surfaces": list(surfaces),
        "judge": judge_name,
        "judge_model": judge_model if judge_name else None,
        "generator_model": app.llm_model,
        "ragas_version": _ragas_version(),
        "warnings": warnings,
        "config": {k: dumped.get(k) for k in _CONFIG_KEYS},
        "settings": redact(dumped),
        "eval_settings": redact(es.model_dump()),
    }


def _write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_reports(
    run_dir: Path,
    run: dict[str, Any],
    items: Sequence[GoldenItem],
    rows: Sequence[SurfaceResult],
    trials: Sequence[NoiseTrial],
    skipped: Sequence[str],
    es: EvalSettings,
) -> dict[str, Any]:
    run["noise_skipped"] = list(skipped)
    summary = summarize(run, items, rows, trials, skipped, es.ks, es.evidence_match_threshold)
    (run_dir / "config.json").write_text(json.dumps(run, indent=2, default=str) + "\n")
    _write_jsonl(run_dir / "results.jsonl", [r.to_dict() for r in rows])
    if trials or skipped:
        _write_jsonl(run_dir / "noise.jsonl", [t.to_dict() for t in trials])
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (run_dir / "summary.md").write_text(render_markdown(summary, es.ks))
    (run_dir / "report.html").write_text(
        render_html(summary, items, rows, es.ks, es.evidence_match_threshold)
    )
    return summary


async def run(
    golden: Path,
    app: Settings,
    es: EvalSettings,
    *,
    surfaces: Sequence[Surface],
    skip_judge: bool = False,
    noise: bool = False,
    limit: int | None = None,
    tags: Sequence[str] = (),
    label: str = "run",
    out_dir: Path | None = None,
    progress: Progress | None = None,
    judges: tuple[Judge, AbstentionCheck] | None = None,
    container: Container | None = None,
) -> Path:
    """Collect → judge → noise sweep → reports. Returns the run folder.

    ``judges`` and ``container`` override :func:`build_judges` / ``build_container`` (tests pass
    a ``FakeJudge`` and a pre-seeded fake corpus).
    """
    say = progress or (lambda _msg: None)
    items = load_golden(golden)
    if tags:
        items = [i for i in items if set(tags) & set(i.tags)]
    if limit is not None:
        items = items[:limit]
    if not items:
        raise ValueError("no golden items left after --tags/--limit filtering")

    # Fail before any work: a judge misconfiguration or model-pin mismatch would otherwise
    # surface only after the (slow) collect phase.
    judge: Judge | None = None
    abstention: AbstentionCheck | None = None
    if not skip_judge:
        judge, abstention = judges or build_judges(app, es)
    container = container or build_container(app, ephemeral_conversations=True)
    await container.store.ensure_ready(app.embed_model, app.embed_dim, es.tenant)

    rows = await collect(container, items, es, surfaces, say)
    by_id = {i.id: i for i in items}
    if judge is not None:
        await judge_results(
            rows,
            by_id,
            judge=judge,
            abstention=abstention,
            concurrency=es.judge_concurrency,
            strip=es.strip_citations,
            progress=say,
        )
    trials: list[NoiseTrial] = []
    skipped: list[str] = []
    if noise:
        find_rows = {r.item_id: r for r in rows if r.surface == "find" and not r.error}
        trials, skipped = await run_noise_sweep(container, items, find_rows, es, judge, say)

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = (out_dir or Path(es.output_dir)) / f"{stamp}-{_slug(label)}"
    run_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(golden, run_dir / "golden.jsonl")
    meta = _run_metadata(label, golden, items, surfaces, app, es, judge.name if judge else None)
    write_reports(run_dir, meta, items, rows, trials, skipped, es)
    return run_dir


def _trial_from_dict(raw: dict[str, Any]) -> NoiseTrial:
    return NoiseTrial(
        item_id=raw["item_id"],
        ratio=raw["ratio"],
        n_gold=raw["n_gold"],
        n_noise=raw["n_noise"],
        response=raw.get("response", ""),
        contexts=[Passage(**p) for p in raw.get("contexts", [])],
        error=raw.get("error"),
    )


async def rejudge(
    run_dir: Path,
    app: Settings,
    es: EvalSettings,
    *,
    progress: Progress | None = None,
    judges: tuple[Judge, AbstentionCheck] | None = None,
) -> dict[str, Any]:
    """Re-score an existing run with the currently configured judge; rewrites its reports."""
    say = progress or (lambda _msg: None)
    run = json.loads((run_dir / "config.json").read_text())
    rows = [record_from_dict(r) for r in _read_jsonl(run_dir / "results.jsonl")]
    collected = {r.item_id for r in rows}
    # The run may have used --tags/--limit: score only the items it actually collected.
    items = [i for i in load_golden(run_dir / "golden.jsonl") if i.id in collected]
    trials = [_trial_from_dict(t) for t in _read_jsonl(run_dir / "noise.jsonl")]
    judge, abstention = judges or build_judges(app, es)
    for row in rows:
        row.scores = {}
    await judge_results(
        rows,
        {i.id: i for i in items},
        judge=judge,
        abstention=abstention,
        concurrency=es.judge_concurrency,
        strip=es.strip_citations,
        progress=say,
    )
    await judge_trials(trials, items, judge, es.judge_concurrency, es.strip_citations)
    run["judge"] = judge.name
    run["judge_model"] = es.judge_model_name(app)
    run["rejudged_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    return write_reports(run_dir, run, items, rows, trials, run.get("noise_skipped", []), es)
