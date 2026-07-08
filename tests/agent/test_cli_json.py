"""Tests for ``agent.cli --json`` NDJSON events and SIGTERM handling (DECISIONS.md D54).

Mirrors ``tests/agent/test_agent.py`` conventions: ``httpx.MockTransport`` stub servers, no live
network, ``main()`` called in-process with an injected client. The SIGTERM test is the one
exception — it needs a real OS process to signal, so it shells out to ``python -m agent.cli``
and still never contacts a real server: ``--server http://127.0.0.1:9`` is the discard port,
refused instantly by the OS, so nothing is ever reached over the network.
"""

from __future__ import annotations

import json
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("httpx")

import httpx  # noqa: E402
from agent.cli import main  # noqa: E402
from agent.client import SiftClient  # noqa: E402

TOKEN = "secret-token"
TENANT = "default"
BASE_URL = "http://testserver"

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler) -> SiftClient:
    return SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler))


def _parse_ndjson(text: str) -> list[dict]:
    """Parse every non-empty line as JSON — raises ``json.JSONDecodeError`` if any line isn't."""
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _empty_manifest_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"tenant": TENANT, "hashes": []})


# --------------------------------------------------------------------------- one-shot --json


def test_dry_run_json_prints_only_valid_ndjson(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.txt").write_bytes(b"alpha")
    (tmp_path / "b.md").write_bytes(b"bravo")

    rc = main([str(tmp_path), "--json", "--dry-run"], client=_client(_empty_manifest_handler))
    out = capsys.readouterr().out

    events = _parse_ndjson(out)  # raises if any line isn't valid JSON — the whole point of (a)
    assert rc == 0
    assert events
    assert all("event" in e for e in events)
    assert events[0]["event"] == "dry_run"
    assert {u["path"] for u in events[0]["would_upload"]} == {"a.txt", "b.md"}


def test_dry_run_json_on_empty_dir_is_still_one_valid_ndjson_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing to upload takes the early-return path — still exactly one well-formed event."""
    rc = main([str(tmp_path), "--json", "--dry-run"], client=_client(_empty_manifest_handler))
    out = capsys.readouterr().out

    events = _parse_ndjson(out)
    assert rc == 0
    assert len(events) == 1
    assert events[0] == {
        "event": "sync",
        "indexed": 0,
        "replaced": 0,
        "deleted": 0,
        "skipped": 0,
        "failed": 0,
        "failures": [],
    }


# --------------------------------------------------------------------------- failures[]


def test_one_shot_json_sync_event_carries_failure_path_and_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A server-rejected file surfaces as ``failures[].path``/``.error`` (closes the D52 gap)."""
    (tmp_path / "good.txt").write_bytes(b"alpha")
    (tmp_path / "bad.xlsx").write_bytes(b"not really an xlsx")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/ingest/manifest":
            return _empty_manifest_handler(request)
        if request.method == "POST" and request.url.path == "/ingest":
            return httpx.Response(
                200,
                json={
                    "tenant": TENANT,
                    "results": [
                        {"path": "good.txt", "status": "indexed"},
                        {
                            "path": "bad.xlsx",
                            "status": "failed",
                            "detail": "xlsx exceeds parse_max_xlsx_cells",
                        },
                    ],
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    rc = main([str(tmp_path), "--json"], client=_client(handler))
    out = capsys.readouterr().out
    events = _parse_ndjson(out)

    assert rc == 0
    assert len(events) == 1
    event = events[0]
    assert event["event"] == "sync"
    assert event["indexed"] == 1
    assert event["failed"] == 1
    assert event["failures"] == [{"path": "bad.xlsx", "error": "xlsx exceeds parse_max_xlsx_cells"}]


def test_human_output_unchanged_without_json_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The flag is fully opt-in — default (no ``--json``) output is exactly as before this."""
    (tmp_path / "a.txt").write_bytes(b"alpha")

    rc = main([str(tmp_path), "--dry-run"], client=_client(_empty_manifest_handler))
    out = capsys.readouterr().out

    assert rc == 0
    assert re.fullmatch(r"WOULD UPLOAD a\.txt \([0-9a-f]{64}\)\n", out)
    with pytest.raises(json.JSONDecodeError):
        json.loads(out)  # human mode must never be accidentally-valid JSON


# --------------------------------------------------------------------------- network failure


def test_dry_run_json_against_unreachable_server_emits_one_fatal_event(tmp_path: Path) -> None:
    """The one-shot path's ``client.manifest()`` call (before the ``--dry-run`` check) used to
    crash with a raw ``httpx.ConnectError`` traceback on stdout, breaking the "every stdout line
    is valid NDJSON" contract. ``--server http://127.0.0.1:9`` (the discard port) is refused
    instantly and purely locally — nothing real is ever contacted — mirroring the SIGTERM test
    above. In ``--json`` mode this must now behave like ``_watch()`` already does: exactly one
    ``{"event": "fatal", ...}`` line on stdout, exit 1, no traceback anywhere on stdout/stderr.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent.cli",
            str(tmp_path),
            "--server",
            "http://127.0.0.1:9",
            "--token",
            "x",
            "--json",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert proc.returncode == 1, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, proc.stdout
    event = json.loads(lines[0])  # raises if the one line isn't valid JSON
    assert event["event"] == "fatal"
    assert "error" in event
    assert "Traceback" not in proc.stderr
    assert "Traceback" not in proc.stdout


def test_dry_run_without_json_against_unreachable_server_still_raises(tmp_path: Path) -> None:
    """Same invocation as above, minus ``--json`` — human-mode behaviour must be byte-for-byte
    unchanged: the connection error still propagates and crashes with a traceback (on stderr,
    since an uncaught exception never touches stdout), exactly as it did before this fix.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent.cli",
            str(tmp_path),
            "--server",
            "http://127.0.0.1:9",
            "--token",
            "x",
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert proc.returncode != 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(proc.stdout)  # human mode: stdout is never JSON, fatal or otherwise
    assert "Traceback" in proc.stderr  # the raw crash — unchanged from before this fix
    assert "ConnectError" in proc.stderr


# --------------------------------------------------------------------------- SIGTERM


@pytest.mark.skipif(not hasattr(signal, "SIGTERM"), reason="SIGTERM unsupported on this platform")
def test_sigterm_stops_watch_mode_cleanly_within_5s(tmp_path: Path) -> None:
    """A real SIGTERM (what a supervisor's ``kill()`` sends — never SIGINT) exits 0 quickly.

    ``--server http://127.0.0.1:9`` (the discard port) fails the initial sync's network call
    fast and purely locally — nothing real is ever contacted — while ``--watch`` still starts
    its filesystem watcher and blocks, exactly the state a Tauri-supervised sidecar sits in
    between syncs.
    """
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "agent.cli",
            str(tmp_path),
            "--server",
            "http://127.0.0.1:9",
            "--token",
            "x",
            "--watch",
            "--json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        time.sleep(1.0)  # let it clear the initial (fast-failing) sync and reach stop_event.wait()
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        pytest.fail("agent.cli --watch did not exit within 5s of SIGTERM")

    assert proc.returncode == 0, err
    events = _parse_ndjson(out)
    assert events, err
    assert events[-1]["event"] == "stopped"
