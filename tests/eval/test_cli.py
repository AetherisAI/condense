"""End to end: a run folder from a seeded fake corpus, re-judging, compare, and the CLI entry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sift.adapters.llm.fake import FakeCompleter
from sift.eval.cli import main
from sift.eval.config import EvalSettings
from sift.eval.judge import AbstentionCheck, FakeJudge
from sift.eval.report import compare
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
