"""Offline tests for the ingestion agent — ``httpx.MockTransport``, no live server.

A single stub handler serves ``GET /ingest/manifest`` and ``POST /ingest``, asserting every
request carries the bearer token and a ``?tenant=`` query param, and records the methods it
saw so a re-run can prove no upload happens when the manifest already knows every hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("httpx")

import httpx  # noqa: E402
from agent.cli import collect, main  # noqa: E402
from agent.client import PartialIngestError, SiftClient  # noqa: E402

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
        # collect() keys are POSIX (upload_name -> as_posix, D45) so the same file maps to the
        # same server path on every OS — a literal forward slash, never str(Path(...)) which is
        # os.sep-dependent and yields "sub\\c.txt" on Windows.
        "sub/c.txt": b"charlie",
    }


# --------------------------------------------------------------------------- collect / diff


def test_collect_hashes_match_sha256(tmp_path: Path) -> None:
    """The digest is the streamed sha256 of the file, and the loader is lazy (not eager bytes).

    A3: ``collect`` must not read every matched file's full bytes up front — the third tuple
    element is a zero-arg callable that only reads the file when actually invoked.
    """
    expected = _seed_dir(tmp_path)
    got = collect(str(tmp_path), {".txt", ".md"})

    by_rel = {rel: (h, loader) for rel, h, loader, _m in got}
    assert set(by_rel) == set(expected)
    for rel, data in expected.items():
        h, loader = by_rel[rel]
        assert callable(loader)
        assert loader() == data
        assert h == hashlib.sha256(data).hexdigest()


def test_collect_filters_by_extension(tmp_path: Path) -> None:
    _seed_dir(tmp_path)
    rels = {rel for rel, _h, _loader, _m in collect(str(tmp_path), {".md"})}
    assert rels == {"b.md"}


def test_collect_skips_oversized_file_and_warns(tmp_path: Path) -> None:
    """A file over the size guard is excluded entirely (never hashed/loaded) and warns (A3)."""
    small = tmp_path / "small.txt"
    small.write_bytes(b"tiny")
    big = tmp_path / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MiB

    with pytest.warns(UserWarning, match="big.txt"):
        got = collect(str(tmp_path), {".txt"}, max_file_size_mb=1)

    rels = {rel for rel, _h, _loader, _m in got}
    assert rels == {"small.txt"}


def test_diff_excludes_known_hashes(tmp_path: Path) -> None:
    _seed_dir(tmp_path)
    files = collect(str(tmp_path), {".txt", ".md"})
    known = {hashlib.sha256(b"alpha").hexdigest()}  # a.txt already ingested

    todo = [(rel, h, loader, m) for rel, h, loader, m in files if h not in known]
    rels = {rel for rel, _h, _loader, _m in todo}
    assert "a.txt" not in rels
    assert "b.md" in rels


# --------------------------------------------------------------------------- client


def test_sift_client_default_timeout_is_600() -> None:
    """One OCR-heavy batch took 5m6s server-side under the old 300s default — raise it so a slow
    but healthy batch isn't abandoned client-side while the server keeps working it."""
    client = SiftClient(BASE_URL, TOKEN)
    try:
        assert client._c.timeout == httpx.Timeout(600.0)
    finally:
        client.close()


def test_sift_client_custom_timeout_reaches_httpx_client() -> None:
    client = SiftClient(BASE_URL, TOKEN, timeout=12.5)
    try:
        assert client._c.timeout == httpx.Timeout(12.5)
    finally:
        client.close()


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


def test_ingest_batches_split_modified_at_and_merge_results() -> None:
    """A folder larger than batch_size goes out in several POSTs; results merge, mtimes split.

    Guards the OOM fix (D29): the client must never send a whole folder as one request. Each
    batch carries only its own files' mtimes, and the merged body keeps the server's top-level
    shape (``tenant``) while concatenating every batch's ``results``.
    """
    posts: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == f"Bearer {TOKEN}"
        tenant = request.url.params.get("tenant")
        assert request.method == "POST" and request.url.path == "/ingest"
        body = request.content.decode("latin-1")
        names = re.findall(r'filename="([^"]*)"', body)
        m = re.search(r'name="modified_at"\r\n\r\n([^\r]*)\r\n', body)
        posts.append({"names": names, "mtimes": json.loads(m.group(1)) if m else {}})
        return httpx.Response(
            200,
            json={"tenant": tenant, "results": [{"path": n, "status": "indexed"} for n in names]},
        )

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler), batch_size=2)
    files = [(f"f{i}.txt", f"data{i}".encode()) for i in range(5)]
    mtimes = {f"f{i}.txt": f"2026-06-30T0{i}:00:00+00:00" for i in range(5)}
    try:
        resp = client.ingest(TENANT, files, modified_at=mtimes)
    finally:
        client.close()

    assert [len(p["names"]) for p in posts] == [2, 2, 1]  # 5 files, batch 2 -> 2+2+1
    assert resp["tenant"] == TENANT  # server shape preserved across the merge
    assert {r["path"] for r in resp["results"]} == {f"f{i}.txt" for i in range(5)}
    for p in posts:  # each POST carried exactly its own batch's mtimes — no cross-batch leakage
        assert set(p["mtimes"]) == set(p["names"])
        assert all(p["mtimes"][n] == mtimes[n] for n in p["names"])


def test_ingest_accepts_lazy_loaders_and_resolves_them_per_batch() -> None:
    """A ``(name, loader)`` pair — not raw bytes — must still upload the loader's bytes (A3)."""
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content.decode("latin-1"))
        results = [{"path": "x", "status": "indexed"}]
        return httpx.Response(200, json={"tenant": "t", "results": results})

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler))
    calls = [0]

    def loader() -> bytes:
        calls[0] += 1
        return b"lazy-bytes"

    try:
        client.ingest("t", [("x.txt", loader)])
    finally:
        client.close()

    assert calls[0] == 1  # read exactly once, at upload time
    assert "lazy-bytes" in bodies[0]


def test_ingest_first_batch_failure_raises_plain_error() -> None:
    """No batch has landed yet — the raw HTTP error propagates, nothing to wrap as partial."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler), batch_size=2)
    try:
        with pytest.raises(httpx.HTTPStatusError):
            client.ingest("t", [("f0.txt", b"d0")])
    finally:
        client.close()


def test_ingest_mid_batch_failure_raises_partial_with_earlier_results() -> None:
    """Batch 2 of 2 fails after batch 1 succeeded — must not lose batch 1's landed results (A4)."""

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("latin-1")
        names = re.findall(r'filename="([^"]*)"', body)
        if "f2.txt" in names:
            return httpx.Response(500, json={"detail": "boom"})
        return httpx.Response(
            200,
            json={"tenant": "t", "results": [{"path": n, "status": "indexed"} for n in names]},
        )

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler), batch_size=2)
    files = [(f"f{i}.txt", f"d{i}".encode()) for i in range(4)]
    try:
        with pytest.raises(PartialIngestError) as exc_info:
            client.ingest("t", files)
    finally:
        client.close()

    partial = exc_info.value.partial
    assert {r["path"] for r in partial["results"]} == {"f0.txt", "f1.txt"}
    assert isinstance(exc_info.value.cause, httpx.HTTPStatusError)
    assert exc_info.value.__cause__ is exc_info.value.cause  # chained via `raise ... from exc`


def test_ingest_mid_batch_invalid_json_raises_partial_with_earlier_results() -> None:
    """Batch 2 of 2 returns HTTP 200 but a body that isn't valid JSON — must still raise
    ``PartialIngestError`` carrying batch 1's landed results (R3): ``r.json()`` used to run
    outside the batch's protected section, so a 200-with-garbage-body silently discarded every
    earlier batch's accounting instead of raising.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("latin-1")
        names = re.findall(r'filename="([^"]*)"', body)
        if "f2.txt" in names:
            return httpx.Response(200, content=b"not json at all")
        return httpx.Response(
            200,
            json={"tenant": "t", "results": [{"path": n, "status": "indexed"} for n in names]},
        )

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler), batch_size=2)
    files = [(f"f{i}.txt", f"d{i}".encode()) for i in range(4)]
    try:
        with pytest.raises(PartialIngestError) as exc_info:
            client.ingest("t", files)
    finally:
        client.close()

    partial = exc_info.value.partial
    assert {r["path"] for r in partial["results"]} == {"f0.txt", "f1.txt"}


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


def test_main_exclude_dir_flag_adds_to_the_builtin_exclusions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--exclude-dir`` merges with the built-in vendored-dir set rather than replacing it."""
    (tmp_path / "keep.txt").write_bytes(b"keep")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "throwaway.txt").write_bytes(b"throwaway")
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "junk.txt").write_bytes(b"venv junk")

    calls: list[str] = []
    client = _client(set(), calls)

    rc = main(
        [str(tmp_path), "--tenant", TENANT, "--exclude-dir", "scratch"],
        client=client,
    )
    client.close()

    assert rc == 0
    out = capsys.readouterr().out
    assert "keep.txt" in out
    assert "throwaway.txt" not in out  # excluded via the flag
    assert "junk.txt" not in out  # still excluded via the built-in default


def test_main_timeout_flag_threads_into_default_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``--timeout`` must reach the ``SiftClient`` ``main`` builds when no ``client`` is injected
    — not just parse as an argparse no-op — and from there into the underlying httpx client."""
    captured: dict[str, float] = {}

    class _RecordingClient(SiftClient):
        def __init__(
            self, base_url: str, token: str, *, timeout: float = 600.0, **kwargs: object
        ) -> None:
            captured["timeout"] = timeout
            super().__init__(
                base_url,
                token,
                timeout=timeout,
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json={"tenant": TENANT, "hashes": []})
                ),
            )

    monkeypatch.setattr("agent.cli.SiftClient", _RecordingClient)

    rc = main(
        [
            "--server",
            BASE_URL,
            "--token",
            TOKEN,
            "--tenant",
            TENANT,
            "--timeout",
            "45",
            str(tmp_path),
        ]
    )

    assert rc == 0
    assert captured["timeout"] == 45.0


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


def test_ingest_sends_modified_at_form_field() -> None:
    # The agent must transmit each file's last-modified time so the server can prefer the newest
    # version at search time. Capture the multipart body and assert the modified_at map is there.
    bodies: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(request.content.decode("latin-1"))
        return httpx.Response(200, json={"tenant": "t", "results": []})

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler))
    client.ingest("t", [("notes.md", b"hi")], modified_at={"notes.md": "2026-02-03T00:00:00+00:00"})
    client.close()

    (body,) = bodies
    assert 'name="modified_at"' in body  # the form field rides alongside the files
    assert "2026-02-03T00:00:00+00:00" in body
    assert "notes.md" in body


def test_main_partial_ingest_prints_statuses_summary_and_exits_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Batch 2 of 2 fails after batch 1 already landed — ``main`` must not swallow that progress
    (R2): every per-file status the server confirmed prints, a ``PARTIAL: …`` summary line names
    how many files never got attempted (including a ``skipped_dedup`` status, same convention as
    ``sync``'s ``Summary.line()``), and the process exits non-zero (never a bare traceback, never
    exit 0 as if nothing went wrong).
    """
    for i, name in enumerate(["a.txt", "b.txt", "c.txt", "d.txt"]):
        (tmp_path / name).write_bytes(f"data-{name}".encode())
        os.utime(tmp_path / name, (1000 + i, 1000 + i))  # controls batch order (mtime-sorted)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/ingest/manifest":
            return httpx.Response(200, json={"tenant": TENANT, "hashes": []})
        if request.method == "POST" and request.url.path == "/ingest":
            body = request.content.decode("latin-1")
            names = re.findall(r'filename="([^"]*)"', body)
            if "c.txt" in names or "d.txt" in names:  # batch 2 (mtime-sorted after a/b) fails
                return httpx.Response(500, json={"detail": "boom"})
            # a.txt already existed server-side (raced with another agent) → skipped_dedup.
            results = [
                {"path": n, "status": "skipped_dedup" if n == "a.txt" else "indexed"} for n in names
            ]
            return httpx.Response(200, json={"tenant": TENANT, "results": results})
        return httpx.Response(404, json={"detail": "not found"})

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler), batch_size=2)

    rc = main(["--tenant", TENANT, str(tmp_path)], client=client)
    client.close()

    assert rc != 0
    out = capsys.readouterr().out
    assert "skipped_dedup\ta.txt" in out
    assert "indexed\tb.txt" in out
    assert "c.txt" not in out.split("PARTIAL:")[0]  # never-attempted files print no status line
    assert "PARTIAL: 1 indexed, 1 skipped, 0 failed, 2 of 4 files never attempted" in out


# --------------------------------------------------------------------------- collect exclusions


def test_collect_prunes_vendored_directories_by_default(tmp_path: Path) -> None:
    """A ``.venv``/``node_modules``/etc. subtree never contributes matches (R4) — a real corpus
    audit found license ``.txt``/``.md`` files under a nested ``.venv/site-packages`` inflating
    the upload set with junk that isn't the user's own content.
    """
    (tmp_path / "real.txt").write_bytes(b"keep me")
    venv = tmp_path / ".venv" / "lib" / "site-packages" / "numpy-1.26.4.dist-info"
    venv.mkdir(parents=True)
    (venv / "LICENSE.txt").write_bytes(b"numpy license junk")
    (tmp_path / ".venv" / "pyvenv.cfg").write_bytes(b"not matched anyway")
    nm = tmp_path / "web" / "node_modules" / "some-pkg"
    nm.mkdir(parents=True)
    (nm / "README.md").write_bytes(b"node_modules junk")

    got = collect(str(tmp_path), {".txt", ".md"})

    rels = {rel for rel, _h, _loader, _m in got}
    assert rels == {"real.txt"}


def test_collect_normal_folders_unaffected_by_exclusion(tmp_path: Path) -> None:
    """A folder that merely *contains* a substring of an excluded name (e.g. ``events``) is not
    excluded — only an exact directory-name match (or a `.dist-info`/`.egg-info` suffix) prunes.
    """
    sub = tmp_path / "events" / "venvoyage"  # neither segment is an excluded name verbatim
    sub.mkdir(parents=True)
    (sub / "notes.txt").write_bytes(b"real content")

    got = collect(str(tmp_path), {".txt"})

    rels = {rel for rel, _h, _loader, _m in got}
    # POSIX key regardless of host OS (upload_name -> as_posix, D45), not str(Path(...)).
    assert rels == {"events/venvoyage/notes.txt"}


def test_collect_prunes_hidden_directories_by_default(tmp_path: Path) -> None:
    """ANY directory whose name starts with ``.`` is pruned, not just the fixed
    ``DEFAULT_EXCLUDE_DIRS`` set — a real corpus ingested ``.session_memory/*.md`` junk that the
    named-set-only check couldn't catch (no name resembling a known vendored-tooling dir)."""
    (tmp_path / "real.md").write_bytes(b"keep me")
    session_memory = tmp_path / ".session_memory"
    session_memory.mkdir()
    (session_memory / "notes.md").write_bytes(b"session memory junk")
    nested_hidden = tmp_path / "sub" / ".cache" / "deep"
    nested_hidden.mkdir(parents=True)
    (nested_hidden / "deep.md").write_bytes(b"nested hidden junk")

    got = collect(str(tmp_path), {".md"})

    rels = {rel for rel, _h, _loader, _m in got}
    assert rels == {"real.md"}


def test_collect_exclude_dirs_is_overridable(tmp_path: Path) -> None:
    """Passing a custom ``exclude_dirs`` (e.g. from ``agent.cli --exclude-dir``) prunes a project-
    specific folder too, on top of (not instead of) the built-in defaults.
    """
    (tmp_path / "keep.txt").write_bytes(b"keep")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "throwaway.txt").write_bytes(b"throwaway")

    from agent.sync import DEFAULT_EXCLUDE_DIRS

    got = collect(str(tmp_path), {".txt"}, exclude_dirs=DEFAULT_EXCLUDE_DIRS | {"scratch"})

    rels = {rel for rel, _h, _loader, _m in got}
    assert rels == {"keep.txt"}


def test_collect_prunes_junk_files_by_default(tmp_path: Path) -> None:
    """``MEMORY.md``/``CLAUDE.md``/``*.tmp`` never contribute matches (D39) — a real corpus audit
    found a stray agent-internal ``MEMORY.md`` polluting an index even though its extension
    (``.md``) is otherwise included.
    """
    (tmp_path / "real.md").write_bytes(b"keep me")
    (tmp_path / "MEMORY.md").write_bytes(b"agent bookkeeping junk")
    (tmp_path / "CLAUDE.md").write_bytes(b"agent bookkeeping junk")
    (tmp_path / "AGENTS.md").write_bytes(b"agent bookkeeping junk")
    (tmp_path / "scratch.tmp").write_bytes(b"scratch junk")
    (tmp_path / ".hidden.md").write_bytes(b"hidden junk")

    got = collect(str(tmp_path), {".md", ".tmp"})

    rels = {rel for rel, _h, _loader, _m in got}
    assert rels == {"real.md"}


def test_collect_normal_files_unaffected_by_exclusion(tmp_path: Path) -> None:
    """A file that merely *contains* an excluded name as a substring (not an exact/glob match) is
    not excluded — only an exact filename or a matching glob pattern prunes.
    """
    (tmp_path / "not-MEMORY.md").write_bytes(b"real content")
    (tmp_path / "MEMORY.md.bak").write_bytes(b"real content too")

    got = collect(str(tmp_path), {".md", ".bak"})

    rels = {rel for rel, _h, _loader, _m in got}
    assert rels == {"not-MEMORY.md", "MEMORY.md.bak"}


def test_collect_exclude_files_is_overridable(tmp_path: Path) -> None:
    """Passing a custom ``exclude_files`` (e.g. from ``agent.cli --exclude-file``) prunes a
    project-specific filename too, on top of (not instead of) the built-in defaults.
    """
    (tmp_path / "keep.txt").write_bytes(b"keep")
    (tmp_path / "draft.txt").write_bytes(b"throwaway")
    (tmp_path / "MEMORY.md").write_bytes(b"still excluded via the built-in default")
    (tmp_path / "keep.md").write_bytes(b"keep")

    from agent.sync import DEFAULT_EXCLUDE_FILES

    got = collect(
        str(tmp_path), {".txt", ".md"}, exclude_files=DEFAULT_EXCLUDE_FILES | {"draft.txt"}
    )

    rels = {rel for rel, _h, _loader, _m in got}
    assert rels == {"keep.txt", "keep.md"}


def test_main_exclude_file_flag_adds_to_the_builtin_exclusions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--exclude-file`` merges with the built-in junk-filename set rather than replacing it."""
    (tmp_path / "keep.txt").write_bytes(b"keep")
    (tmp_path / "draft.txt").write_bytes(b"throwaway")
    (tmp_path / "MEMORY.md").write_bytes(b"agent junk")

    calls: list[str] = []
    client = _client(set(), calls)

    rc = main(
        [str(tmp_path), "--tenant", TENANT, "--exclude-file", "draft.txt"],
        client=client,
    )
    client.close()

    assert rc == 0
    out = capsys.readouterr().out
    assert "keep.txt" in out
    assert "draft.txt" not in out  # excluded via the flag
    assert "MEMORY.md" not in out  # still excluded via the built-in default
