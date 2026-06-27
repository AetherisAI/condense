"""Offline tests for the ingestion agent — ``httpx.MockTransport``, no live server.

A single stub handler serves ``GET /ingest/manifest`` and ``POST /ingest``, asserting every
request carries the bearer token and a ``?tenant=`` query param, and records the methods it
saw so a re-run can prove no upload happens when the manifest already knows every hash.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("httpx")

import httpx  # noqa: E402
from agent.cli import collect, main  # noqa: E402
from agent.client import SiftClient  # noqa: E402

TOKEN = "secret-token"
TENANT = "team-a"
BASE_URL = "http://testserver"

Handler = Callable[[httpx.Request], httpx.Response]


def _make_handler(known: set[str], calls: list[str], token: str = TOKEN) -> Handler:
    """A stub server: serves the manifest from ``known`` and echoes uploads as ``indexed``."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == f"Bearer {token}"
        tenant = request.url.params.get("tenant")
        assert tenant is not None
        calls.append(request.method)
        if request.method == "GET" and request.url.path == "/ingest/manifest":
            return httpx.Response(200, json={"tenant": tenant, "hashes": sorted(known)})
        if request.method == "POST" and request.url.path == "/ingest":
            body = request.content.decode("latin-1")
            assert 'name="files"' in body
            names = re.findall(r'filename="([^"]*)"', body)
            results = [{"path": name, "status": "indexed"} for name in names]
            return httpx.Response(200, json={"tenant": tenant, "results": results})
        return httpx.Response(404, json={"detail": "not found"})

    return handler


def _client(known: set[str], calls: list[str]) -> SiftClient:
    transport = httpx.MockTransport(_make_handler(known, calls))
    return SiftClient(BASE_URL, TOKEN, transport=transport)


def _seed_dir(root: Path) -> dict[str, bytes]:
    """Write a small tree (mixed extensions) under ``root``; return matched rel->bytes."""
    (root / "a.txt").write_bytes(b"alpha")
    (root / "b.md").write_bytes(b"bravo")
    sub = root / "sub"
    sub.mkdir()
    (sub / "c.txt").write_bytes(b"charlie")
    (root / "skip.log").write_bytes(b"ignored")  # excluded extension
    return {
        "a.txt": b"alpha",
        "b.md": b"bravo",
        str(Path("sub") / "c.txt"): b"charlie",
    }


# --------------------------------------------------------------------------- collect / diff


def test_collect_hashes_match_sha256(tmp_path: Path) -> None:
    expected = _seed_dir(tmp_path)
    got = collect(str(tmp_path), {".txt", ".md"})

    by_rel = {rel: (h, data) for rel, h, data in got}
    assert set(by_rel) == set(expected)
    for rel, data in expected.items():
        h, got_data = by_rel[rel]
        assert got_data == data
        assert h == hashlib.sha256(data).hexdigest()


def test_collect_filters_by_extension(tmp_path: Path) -> None:
    _seed_dir(tmp_path)
    rels = {rel for rel, _h, _data in collect(str(tmp_path), {".md"})}
    assert rels == {"b.md"}


def test_diff_excludes_known_hashes(tmp_path: Path) -> None:
    _seed_dir(tmp_path)
    files = collect(str(tmp_path), {".txt", ".md"})
    known = {hashlib.sha256(b"alpha").hexdigest()}  # a.txt already ingested

    todo = [(rel, h, data) for rel, h, data in files if h not in known]
    rels = {rel for rel, _h, _data in todo}
    assert "a.txt" not in rels
    assert "b.md" in rels


# --------------------------------------------------------------------------- client


def test_manifest_parses_and_sends_bearer_and_tenant() -> None:
    calls: list[str] = []
    known = {"h1", "h2"}
    client = _client(known, calls)
    try:
        assert client.manifest(TENANT) == known
    finally:
        client.close()
    assert calls == ["GET"]


def test_ingest_posts_multipart_and_parses_results() -> None:
    calls: list[str] = []
    client = _client(set(), calls)
    try:
        resp = client.ingest(TENANT, [("a.txt", b"alpha"), ("b.md", b"bravo")])
    finally:
        client.close()
    assert calls == ["POST"]
    assert resp["tenant"] == TENANT
    statuses = {r["path"]: r["status"] for r in resp["results"]}
    assert statuses == {"a.txt": "indexed", "b.md": "indexed"}


# --------------------------------------------------------------------------- main end-to-end


def test_main_uploads_new_files_and_prints_statuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _seed_dir(tmp_path)
    calls: list[str] = []
    client = _client(set(), calls)  # server knows nothing → everything uploads

    rc = main(["--tenant", TENANT, str(tmp_path)], client=client)
    client.close()

    assert rc == 0
    assert "GET" in calls and "POST" in calls
    out = capsys.readouterr().out
    assert "indexed" in out
    assert "a.txt" in out and "b.md" in out


def test_main_dry_run_makes_no_post(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _seed_dir(tmp_path)
    calls: list[str] = []
    client = _client(set(), calls)

    rc = main(["--tenant", TENANT, "--dry-run", str(tmp_path)], client=client)
    client.close()

    assert rc == 0
    assert "POST" not in calls
    assert "WOULD UPLOAD" in capsys.readouterr().out


def test_main_rerun_all_known_skips_upload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    contents = _seed_dir(tmp_path)
    all_hashes = {hashlib.sha256(data).hexdigest() for data in contents.values()}
    calls: list[str] = []
    client = _client(all_hashes, calls)  # manifest already knows every file

    rc = main(["--tenant", TENANT, str(tmp_path)], client=client)
    client.close()

    assert rc == 0
    assert "POST" not in calls
    assert "nothing to upload" in capsys.readouterr().out
