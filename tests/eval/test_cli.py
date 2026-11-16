"""End to end: a run folder from a seeded fake corpus, re-judging, compare, and the CLI entry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sift.adapters.llm.fake import FakeCompleter
from sift.eval.cli import main
from sift.eval.config import EvalSettings
from sift.eval.judge import AbstentionCheck, FakeJudge
from sift.eval.report import check_regressions, compare, render_gate
from sift.eval.runner import redact, rejudge, run
from sift.factory import Container

GOLDEN = [
    {
        "id": "refunds",
        "question": "refunds take two to three business days after approval",
        "reference": "Two to three business days.",
        "relevant": [{"path": "refunds.md", "evidence": "two to three business days"}],
        "tags": ["policy"],
    },
    {
        "id": "express",
        "question": "express shipping arrives the next business day",
        "reference": "The next business day.",
        "relevant": [{"path": "shipping.md", "page": 2}],
        "tags": ["policy", "shipping"],
    },
    {"id": "moon", "question": "who owns the moon?", "answerable": False},
]


@pytest.fixture
def golden(tmp_path: Path) -> Path:
    path = tmp_path / "golden.jsonl"
    path.write_text("# test set\n" + "\n".join(json.dumps(g) for g in GOLDEN) + "\n")
    return path


async def test_run_writes_a_complete_run_folder(
    container: Container, golden: Path, tmp_path: Path
) -> None:
    judges = (FakeJudge({"answer_correctness": 0.9}), AbstentionCheck(FakeCompleter("NO")))

    run_dir = await run(
        golden,
        container.settings,
        EvalSettings(warmup=0, noise_ratios="0,0.5", noise_context_size=2),
        surfaces=["find", "ask"],
        noise=True,
        label="baseline run",
        out_dir=tmp_path / "runs",
        judges=judges,
        container=container,
    )

    assert run_dir.name.endswith("-baseline-run")
    names = {p.name for p in run_dir.iterdir()}
    assert names == {
        "config.json",
        "golden.jsonl",
        "results.jsonl",
        "noise.jsonl",
        "summary.json",
        "summary.md",
        "report.html",
    }
    summary = json.loads((run_dir / "summary.json").read_text())
    find = summary["surfaces"]["find"]
    # Exact-text questions over the fake embedder → the gold doc is retrieved first.
    assert find["retrieval"]["final"]["doc"]["hit@1"] == 1.0
    assert find["retrieval"]["retrieved"]["chunk"]["recall@1"] == 1.0
    assert find["answer"]["answer_correctness"] == {"n": 2, "failed": 0, "mean": 0.9}
    assert find["abstention"]["correct_abstention"]["mean"] == 0.0  # FakeCompleter says "NO"
    assert {"embed", "retrieve", "total"} <= set(find["latency_ms"])
    assert summary["surfaces"]["ask"]["tool_calls_mean"] == 0.0  # NullCompleter calls no tool
    assert [r["ratio"] for r in summary["noise"]["by_ratio"]] == [0.0, 0.5]
    assert summary["tags"]["shipping"]["n"] == 1
    # By-tag rows carry every judged metric, so variants are compared within their own tag.
    assert summary["tags"]["shipping"]["find.answer_correctness"] == 0.9
    assert summary["tags"]["shipping"]["find.answer_relevancy"] == 0.5
    config = json.loads((run_dir / "config.json").read_text())
    assert config["settings"]["ingest_token"] == "set"  # redacted, never the value
    assert config["judge"] == "fake"
    html = (run_dir / "report.html").read_text()
    assert "<title>sift-eval baseline run</title>" in html
    assert "who owns the moon?" in html
    assert "## Find" in (run_dir / "summary.md").read_text()


async def test_rejudge_rescores_and_compare_diffs(
    container: Container, golden: Path, tmp_path: Path
) -> None:
    es = EvalSettings(warmup=0)
    first = await run(
        golden,
        container.settings,
        es,
        surfaces=["find"],
        out_dir=tmp_path,
        label="a",
        judges=(FakeJudge({"answer_correctness": 0.4}), AbstentionCheck(FakeCompleter("NO"))),
        container=container,
    )
    before = json.loads((first / "summary.json").read_text())

    after = await rejudge(
        first,
        container.settings,
        es,
        judges=(FakeJudge({"answer_correctness": 0.8}), AbstentionCheck(FakeCompleter("NO"))),
    )

    assert after["surfaces"]["find"]["answer"]["answer_correctness"]["mean"] == 0.8
    table = compare(before, after)
    assert "find.answer.answer_correctness.mean | 0.400 | 0.800 | +0.400 | ▲ better" in table
    assert "find.latency_ms.total.mean" in table  # unchanged rows still listed
    assert "Different golden sets" not in table  # same file: no warning
    assert "find.retrieval.final.doc.complete@1" in table


async def test_rejudge_with_metrics_keeps_every_other_score(
    container: Container, golden: Path, tmp_path: Path
) -> None:
    es = EvalSettings(warmup=0)
    first = await run(
        golden,
        container.settings,
        es,
        surfaces=["find"],
        out_dir=tmp_path,
        label="a",
        judges=(FakeJudge({"answer_recall": 0.0}), AbstentionCheck(FakeCompleter("NO"))),
        container=container,
    )
    judge = FakeJudge({"answer_recall": 1.0, "faithfulness": 0.1})

    after = await rejudge(
        first,
        container.settings,
        es,
        judges=(judge, AbstentionCheck(FakeCompleter("YES"))),
        metrics=["answer_recall"],
    )

    answer = after["surfaces"]["find"]["answer"]
    assert answer["answer_recall"]["mean"] == 1.0
    assert answer["faithfulness"]["mean"] == 0.5  # the first judge's score, not re-scored
    assert {metric for metric, _ in judge.calls} == {"answer_recall"}
    # Abstention isn't re-asked either: still the first run's "NO".
    assert after["surfaces"]["find"]["abstention"]["correct_abstention"]["mean"] == 0.0
    config = json.loads((first / "config.json").read_text())
    assert config["rejudged_metrics"] == ["answer_recall"]


def test_judge_rejects_unknown_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["judge", "eval-runs/x", "--metrics", "answer_recal"])

    assert "metrics must be a subset of" in capsys.readouterr().err


def test_compare_warns_when_the_golden_set_changed() -> None:
    def summary(sha: str, n: int) -> dict[str, object]:
        return {
            "run": {"label": sha, "golden_sha256": sha * 16, "n_items": n},
            "surfaces": {"find": {"retrieval": {"final": {"doc": {"recall@1": 0.5}}}}},
        }

    table = compare(summary("aaaa", 10), summary("bbbb", 12))

    assert (
        "**Different golden sets** (A aaaaaaaaaaaa…, 10 items; B bbbbbbbbbbbb…, 12 items)" in table
    )


def test_compare_treats_latency_as_lower_is_better() -> None:
    a = {"run": {"label": "a"}, "surfaces": {"find": {"latency_ms": {"total": {"p50": 100.0}}}}}
    b = {"run": {"label": "b"}, "surfaces": {"find": {"latency_ms": {"total": {"p50": 80.0}}}}}

    assert "▲ better" in compare(a, b)


def test_redact_matches_credential_suffixes_only() -> None:
    out = redact(
        {
            "llm_api_key": "sk-1",
            "judge_api_key": "",
            "turso_auth_token": "t",
            "auth_tokens": "a:b",
            "answer_max_tokens": 900,
            "chunk_tokenizer": "auto",
        }
    )

    assert out == {
        "llm_api_key": "set",
        "judge_api_key": None,
        "turso_auth_token": "set",
        "auth_tokens": "set",
        "answer_max_tokens": 900,
        "chunk_tokenizer": "auto",
    }


def test_cli_run_skip_judge_on_an_empty_default_store(
    golden: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / "eval.env"
    env.write_text(f"STORE_BACKEND=fake\nEVAL_WARMUP=0\nEVAL_OUTPUT_DIR={tmp_path / 'runs'}\n")

    code = main(["--env-file", str(env), "run", "--golden", str(golden), "--skip-judge"])

    out = capsys.readouterr()
    assert code == 0
    assert "report: " in out.out
    assert "[find 3/3] moon" in out.err
    (run_dir,) = (tmp_path / "runs").iterdir()
    assert json.loads((run_dir / "config.json").read_text())["judge"] is None


def test_cli_reports_golden_errors_with_exit_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": "x"}\n')

    code = main(["run", "--golden", str(bad), "--skip-judge"])

    assert code == 2
    assert "bad.jsonl:1 (x): 'question' must be a non-empty string" in capsys.readouterr().err


def test_cli_compare(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for name, value in (("a", 0.5), ("b", 0.75)):
        (tmp_path / name).mkdir()
        summary = {"run": {"label": name}, "surfaces": {"find": {"answer": {"x": {"mean": value}}}}}
        (tmp_path / name / "summary.json").write_text(json.dumps(summary))

    assert main(["compare", str(tmp_path / "a"), str(tmp_path / "b")]) == 0
    assert "find.answer.x.mean | 0.500 | 0.750 | +0.250 | ▲ better" in capsys.readouterr().out


# --- compare --fail-on: the regression gate -----------------------------------------------------

HIT1 = "find.retrieval.final.doc.hit@1"


def _gate_summary(hit1: float, p50: float = 100.0, sha: str = "a" * 64) -> dict[str, object]:
    return {
        "run": {"label": "x", "golden_sha256": sha, "n_items": 75},
        "surfaces": {
            "find": {
                "retrieval": {"final": {"doc": {"hit@1": hit1}}},
                "latency_ms": {"total": {"p50": p50}},
            }
        },
    }


def test_gate_fails_only_when_a_metric_worsens_beyond_its_tolerance() -> None:
    within, beyond = (
        check_regressions(_gate_summary(0.60), _gate_summary(cand), {HIT1: 0.03})[0]
        for cand in (0.58, 0.56)
    )

    assert not within.failed
    assert render_gate([within]).count("+0.020") == 1
    assert beyond.failed
    assert beyond.worse_by == pytest.approx(0.04)


def test_gate_prints_an_unchanged_metric_as_zero_not_minus_zero() -> None:
    (check,) = check_regressions(_gate_summary(0.6), _gate_summary(0.6), {HIT1: 0.03})

    assert "| +0.000 |" in render_gate([check])


def test_gate_ignores_improvements_and_knows_lower_is_better() -> None:
    p50 = "find.latency_ms.total.p50"
    better, slower = (
        check_regressions(_gate_summary(0.6, a), _gate_summary(0.9, b), {HIT1: 0.0, p50: 10.0})
        for a, b in ((100.0, 50.0), (100.0, 120.0))
    )

    assert [c.failed for c in better] == [False, False]
    assert [c.failed for c in slower] == [False, True]


def test_gate_rejects_an_unknown_metric() -> None:
    with pytest.raises(ValueError, match="hit@1x"):
        check_regressions(_gate_summary(0.6), _gate_summary(0.6), {"find.hit@1x": 0.03})


def test_gate_refuses_runs_over_different_golden_sets() -> None:
    with pytest.raises(ValueError, match="different golden sets"):
        check_regressions(_gate_summary(0.6), _gate_summary(0.6, sha="b" * 64), {HIT1: 0.03})


@pytest.mark.parametrize(
    ("candidate", "code", "verdict"), [(0.58, 0, "passed"), (0.5, 1, "FAILED")]
)
def test_cli_compare_fail_on_sets_the_exit_code(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    candidate: float,
    code: int,
    verdict: str,
) -> None:
    for name, value in (("base", 0.6), ("cand", candidate)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "summary.json").write_text(json.dumps(_gate_summary(value)))

    argv = ["compare", str(tmp_path / "base"), str(tmp_path / "cand"), "--fail-on", f"{HIT1}:0.03"]

    assert main(argv) == code
    out = capsys.readouterr().out
    assert "## Regression gate" in out
    assert f"**{verdict}**" in out


@pytest.mark.parametrize("limit", ["hit@1", ":0.03", "hit@1:x", "hit@1:nan"])
def test_cli_compare_fail_on_rejects_a_malformed_limit(
    capsys: pytest.CaptureFixture[str], limit: str
) -> None:
    with pytest.raises(SystemExit):
        main(["compare", "a", "b", "--fail-on", limit])

    assert "METRIC:TOLERANCE" in capsys.readouterr().err
