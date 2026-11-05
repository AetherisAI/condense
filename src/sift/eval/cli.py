"""``sift-eval`` — the command line (argparse, like ``agent/cli.py``).

    sift-eval run --golden evals/golden.jsonl [--surfaces find,ask] [--skip-judge] [--noise]
    sift-eval judge eval-runs/<run>            # re-score a run with the current judge
    sift-eval compare eval-runs/<a> eval-runs/<b>
    sift-eval validate --golden evals/golden.jsonl
    sift-eval bootstrap --out evals/draft.jsonl [--n 30]

Configuration comes from the same ``.env`` the server reads (``--env-file`` to point elsewhere)
plus the ``EVAL_*`` keys (``sift.eval.config``). Progress goes to stderr; the final summary to
stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from sift.core.errors import SiftError
from sift.eval.config import load_settings
from sift.eval.golden import GoldenError
from sift.eval.records import SURFACES, Surface
from sift.eval.report import compare


def _progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _surfaces(raw: str) -> list[Surface]:
    chosen = _csv(raw)
    unknown = set(chosen) - set(SURFACES)
    if unknown or not chosen:
        raise argparse.ArgumentTypeError(f"surfaces must be a subset of {', '.join(SURFACES)}")
    return cast(list[Surface], chosen)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sift-eval", description="Evaluate Condense quality")
    parser.add_argument("--env-file", type=Path, help="config file (default: ./.env)")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="collect, judge and report one run")
    run.add_argument("--golden", type=Path, required=True, help="golden JSONL file")
    run.add_argument("--surfaces", type=_surfaces, default=list(SURFACES), help="find,ask")
    run.add_argument("--skip-judge", action="store_true", help="retrieval + latency only")
    run.add_argument("--noise", action="store_true", help="also run the noise-robustness sweep")
    run.add_argument("--limit", type=int, help="only the first N questions")
    run.add_argument("--tags", type=_csv, default=[], help="only questions with any of these")
    run.add_argument("--label", default="run", help="name for the run folder and report")
    run.add_argument("--out", type=Path, help="output directory (default: EVAL_OUTPUT_DIR)")

    judge = sub.add_parser("judge", help="re-score an existing run with the current judge")
    judge.add_argument("run_dir", type=Path)

    comp = sub.add_parser("compare", help="diff two runs' summaries (B relative to A)")
    comp.add_argument("run_a", type=Path)
    comp.add_argument("run_b", type=Path)

    validate = sub.add_parser("validate", help="check a golden set against the index")
    validate.add_argument("--golden", type=Path, required=True)

    boot = sub.add_parser("bootstrap", help="draft golden items from the index for curation")
    boot.add_argument("--out", type=Path, required=True)
    boot.add_argument("--n", type=int, default=30, help="how many drafts to aim for")
    return parser


def _headline(run_dir: Path) -> str:
    summary = json.loads((run_dir / "summary.json").read_text())
    lines = [f"run: {run_dir}", f"report: {run_dir / 'report.html'}"]
    find = summary["surfaces"].get("find", {})
    if find.get("retrieval"):
        doc = find["retrieval"]["final"]["doc"]
        lines.append(f"find top-1 doc accuracy: {doc.get('hit@1', 0):.3f}")
    for name, data in summary["surfaces"].items():
        correctness = data.get("answer", {}).get("answer_correctness", {})
        if "mean" in correctness:
            lines.append(f"{name} answer correctness: {correctness['mean']:.3f}")
        if data.get("errors"):
            lines.append(f"{name}: {data['errors']} question(s) errored — see report")
    return "\n".join(lines)


async def _dispatch(args: argparse.Namespace) -> int:
    from sift.eval import runner

    if args.command == "compare":
        a = json.loads((args.run_a / "summary.json").read_text())
        b = json.loads((args.run_b / "summary.json").read_text())
        print(compare(a, b), end="")
        return 0

    app, es = load_settings(args.env_file)
    if args.command == "run":
        run_dir = await runner.run(
            args.golden,
            app,
            es,
            surfaces=args.surfaces,
            skip_judge=args.skip_judge,
            noise=args.noise,
            limit=args.limit,
            tags=args.tags,
            label=args.label,
            out_dir=args.out,
            progress=_progress,
        )
        print(_headline(run_dir))
        return 0
    if args.command == "judge":
        await runner.rejudge(args.run_dir, app, es, progress=_progress)
        print(_headline(args.run_dir))
        return 0
    if args.command == "validate":
        from sift.eval.validate import validate_golden

        report = await validate_golden(args.golden, app, es)
        print(report.render())
        return 1 if report.errors else 0
    if args.command == "bootstrap":
        from sift.eval.bootstrap import bootstrap

        written = await bootstrap(args.out, app, es, n=args.n, progress=_progress)
        print(f"wrote {written} draft item(s) to {args.out} — review every one before use")
        return 0
    raise AssertionError(args.command)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return asyncio.run(_dispatch(args))
    except (GoldenError, SiftError, RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"sift-eval: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
