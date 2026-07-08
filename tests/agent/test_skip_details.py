"""Tests for local skip-decision visibility (``SkipDetail``/``Summary.skipped_details``).

``Summary.failures`` (D52/D54) already names every file the *server* rejected. These tests cover
the complementary local half: every skip decision the agent makes on its own — before a request
is ever sent — named in a caller-supplied ``skip_sink`` and threaded end-to-end into
``Summary.skipped_details``, so a caller (``agent.cli --json``, the desktop app) can tell "never
attempted, and here's why" apart from "attempted and the server said no". Offline only —
``httpx.MockTransport``, no live server, same conventions as ``test_sync.py``/``test_agent.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("httpx")

import httpx  # noqa: E402
from agent.client import SiftClient  # noqa: E402
from agent.sync import SkipDetail, collect, collect_roots, sync  # noqa: E402

TOKEN = "secret-token"
BASE_URL = "http://testserver"


# --------------------------------------------------------------------------- collect / skip_sink


def test_collect_skip_sink_records_oversized_file(tmp_path: Path) -> None:
    (tmp_path / "small.txt").write_bytes(b"tiny")
    (tmp_path / "big.txt").write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MiB

    sink: list[SkipDetail] = []
    with pytest.warns(UserWarning, match="big.txt"):
        collect(str(tmp_path), {".txt"}, max_file_size_mb=1, skip_sink=sink)

    assert SkipDetail(path="big.txt", reason="oversized") in sink


def test_collect_skip_sink_records_unsupported_extension(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"keep")
    (tmp_path / "notes.log").write_bytes(b"ignored extension")

    sink: list[SkipDetail] = []
    got = collect(str(tmp_path), {".txt"}, skip_sink=sink)

    assert {rel for rel, _h, _loader, _m in got} == {"a.txt"}
    assert SkipDetail(path="notes.log", reason="unsupported_extension") in sink


def test_collect_skip_sink_records_excluded_file(tmp_path: Path) -> None:
    (tmp_path / "real.md").write_bytes(b"keep")
    (tmp_path / "MEMORY.md").write_bytes(b"agent bookkeeping junk")

    sink: list[SkipDetail] = []
    collect(str(tmp_path), {".md"}, skip_sink=sink)

    assert SkipDetail(path="MEMORY.md", reason="excluded_file") in sink


def test_collect_skip_sink_one_entry_per_pruned_dir_not_per_file_inside(tmp_path: Path) -> None:
    """A pruned dir (``.venv`` etc.) gets ONE ``excluded_dir`` entry, however many files it holds
    — enumerating every file inside would defeat the point of pruning the walk at all.
    """
    (tmp_path / "real.txt").write_bytes(b"keep")
    venv = tmp_path / ".venv" / "site-packages"
    venv.mkdir(parents=True)
    (venv / "a.txt").write_bytes(b"junk1")
    (venv / "b.txt").write_bytes(b"junk2")

    sink: list[SkipDetail] = []
    collect(str(tmp_path), {".txt"}, skip_sink=sink)

    excluded_dir_entries = [s for s in sink if s.reason == "excluded_dir"]
    assert len(excluded_dir_entries) == 1
    assert excluded_dir_entries[0].path == ".venv"


def test_collect_skip_sink_omitted_by_default_behaves_exactly_as_before(tmp_path: Path) -> None:
    """``skip_sink`` is fully opt-in — every pre-existing caller (default ``None``) is unaffected,
    same as ``collect()`` without it always has been."""
    (tmp_path / "a.txt").write_bytes(b"keep")
    (tmp_path / "notes.log").write_bytes(b"ignored")

    got = collect(str(tmp_path), {".txt"})

    assert {rel for rel, _h, _loader, _m in got} == {"a.txt"}


def test_collect_skip_sink_is_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A huge tree of non-matching files can't balloon ``skip_sink`` past the cap."""
    import agent.sync as sync_mod

    monkeypatch.setattr(sync_mod, "_MAX_SKIP_DETAILS", 3)
    for i in range(10):
        (tmp_path / f"junk{i}.log").write_bytes(b"x")

    sink: list[SkipDetail] = []
    collect(str(tmp_path), {".txt"}, skip_sink=sink)

    assert len(sink) == 3


def test_collect_roots_skip_sink_aggregates_across_roots(tmp_path: Path) -> None:
    root_a = tmp_path / "A"
    root_b = tmp_path / "B"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "keep.txt").write_bytes(b"keep")
    (root_a / "skip.log").write_bytes(b"skip a")
    (root_b / "skip.log").write_bytes(b"skip b")

    sink: list[SkipDetail] = []
    collect_roots([str(root_a), str(root_b)], {".txt"}, skip_sink=sink)

    unsupported = [s for s in sink if s.reason == "unsupported_extension"]
    assert len(unsupported) == 2  # one from each root, not deduped by relative name


# --------------------------------------------------------------------------- sync() end-to-end


def _handler(docs: dict[str, str]):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == f"Bearer {TOKEN}"
        if request.method == "GET" and request.url.path == "/documents":
            documents = [{"path": p, "source_hash": h, "chunks": 1} for p, h in docs.items()]
            return httpx.Response(
                200, json={"tenant": "default", "documents": documents, "supported": True}
            )
        if request.method == "POST" and request.url.path == "/ingest":
            body = request.content.decode("latin-1")
            names = re.findall(r'filename="([^"]*)"', body)
            results = [{"path": name, "status": "indexed", "chunks": 1} for name in names]
            return httpx.Response(200, json={"tenant": "default", "results": results})
        return httpx.Response(404, json={"detail": "not found"})

    return handler


def _client(docs: dict[str, str]) -> SiftClient:
    return SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(_handler(docs)))


def test_sync_summary_carries_skipped_details_for_oversized_file(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_bytes(b"keep")
    (tmp_path / "huge.txt").write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MiB

    with pytest.warns(UserWarning, match="huge.txt"):
        summary = sync(_client({}), str(tmp_path), {".txt"}, max_file_size_mb=1)

    assert summary.skipped_details == (SkipDetail(path="huge.txt", reason="oversized"),)


def test_sync_summary_carries_skipped_details_even_on_documents_network_failure(
    tmp_path: Path,
) -> None:
    """The local collect pass runs BEFORE ``/documents`` is ever called — its skip decisions must
    survive an early network-failure return, not just the happy path.
    """
    (tmp_path / "notes.log").write_bytes(b"unsupported extension")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler))
    summary = sync(client, str(tmp_path), {".txt"})

    assert summary.error is not None
    expected = (SkipDetail(path="notes.log", reason="unsupported_extension"),)
    assert summary.skipped_details == expected


def test_sync_summary_skipped_details_empty_when_nothing_locally_skipped(tmp_path: Path) -> None:
    (tmp_path / "keep.txt").write_bytes(b"keep")

    summary = sync(_client({}), str(tmp_path), {".txt"})

    assert summary.skipped_details == ()
