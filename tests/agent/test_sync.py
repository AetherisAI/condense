"""Offline tests for the replace-aware sync engine — ``httpx.MockTransport``, no live server.

A stub server backs ``GET /documents``, ``POST /ingest``, and ``DELETE /documents/{hash}`` from
an in-memory ``{path: source_hash}`` map, recording every request so the tests can assert the
*exact* add/replace/skip/delete behaviour (and that identical files never re-upload).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path, PurePath

import pytest

pytest.importorskip("httpx")

import httpx  # noqa: E402
from agent.client import SiftClient  # noqa: E402
from agent.sync import collect, reconcile, sync  # noqa: E402

TOKEN = "secret-token"
BASE_URL = "http://testserver"

Handler = Callable[[httpx.Request], httpx.Response]


def _server(docs: dict[str, str], calls: list[tuple[str, str]], *, supported: bool = True):
    """A stub engine: ``docs`` is ``{path: source_hash}``, mutated by ingest/delete like real."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == f"Bearer {TOKEN}"
        path = request.url.path
        calls.append((request.method, path))

        if request.method == "GET" and path == "/documents":
            documents = [
                {"path": p, "source_hash": h, "chunks": 1} for p, h in sorted(docs.items())
            ]
            body = {"tenant": "default", "documents": documents, "supported": supported}
            return httpx.Response(200, json=body)

        if request.method == "POST" and path == "/ingest":
            # Parse multipart filenames + bytes well enough to register their content hash.
            body = request.content
            results = []
            for name, data in _parse_multipart(body):
                docs[name] = hashlib.sha256(data).hexdigest()
                results.append({"path": name, "status": "indexed", "chunks": 1})
            return httpx.Response(200, json={"tenant": "default", "results": results})

        if request.method == "DELETE" and path.startswith("/documents/"):
            victim = path.rsplit("/", 1)[-1]
            removed = [p for p, h in docs.items() if h == victim]
            for p in removed:
                del docs[p]
            return httpx.Response(
                200,
                json={"tenant": "default", "source_hash": victim, "deleted_chunks": len(removed)},
            )

        return httpx.Response(404, json={"detail": "not found"})

    return handler


def _parse_multipart(body: bytes) -> list[tuple[str, bytes]]:
    """Tiny multipart reader: yield (filename, raw-bytes) for each ``files`` part."""
    text = body.split(b"\r\n")
    out: list[tuple[str, bytes]] = []
    i = 0
    while i < len(text):
        line = text[i]
        if b'filename="' in line:
            name = line.split(b'filename="', 1)[1].split(b'"', 1)[0].decode()
            i += 1
            while i < len(text) and text[i] != b"":  # skip remaining part headers
                i += 1
            i += 1  # blank line before the body
            data = text[i] if i < len(text) else b""
            out.append((name, data))
        i += 1
    return out


def _client(handler: Handler) -> SiftClient:
    return SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler))


def _abs(base: Path, name: str) -> str:
    """The absolute POSIX upload key the continuous sync assigns a file (see collect_roots)."""
    return PurePath(str(base / name)).as_posix()


# --------------------------------------------------------------------------- collect / reconcile


def test_collect_normalises_to_posix(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_bytes(b"charlie")
    names = {name for name, _h, _d in collect(str(tmp_path), {".txt"})}
    assert names == {"sub/c.txt"}  # forward slash regardless of OS


def test_reconcile_classifies_each_path() -> None:
    local = {"new.md": "hnew", "same.md": "h1", "changed.md": "h2new"}
    remote = {"same.md": "h1", "changed.md": "h2old", "gone.md": "hgone"}

    keep = reconcile(local, remote, delete_removed=False)
    assert set(keep.ingest) == {"new.md", "changed.md"}
    assert keep.skip == ["same.md"]
    assert keep.replace == ["changed.md"]
    assert keep.delete_hashes == ["h2old"]  # only the superseded version

    purge = reconcile(local, remote, delete_removed=True)
    assert set(purge.delete_hashes) == {"h2old", "hgone"}  # plus the vanished file


# --------------------------------------------------------------------------- sync end-to-end


def test_sync_ingests_new_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes(b"alpha")
    calls: list[tuple[str, str]] = []
    docs: dict[str, str] = {}
    client = _client(_server(docs, calls))
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()
    assert summary.indexed == 1 and summary.replaced == 0 and summary.deleted == 0
    assert docs == {_abs(tmp_path, "a.md"): hashlib.sha256(b"alpha").hexdigest()}


def test_sync_skips_identical_without_upload(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes(b"alpha")
    calls: list[tuple[str, str]] = []
    docs = {_abs(tmp_path, "a.md"): hashlib.sha256(b"alpha").hexdigest()}
    client = _client(_server(docs, calls))
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()
    assert summary.skipped == 1 and summary.indexed == 0
    assert ("POST", "/ingest") not in calls  # no upload for a byte-identical file


def test_sync_replaces_changed_file_and_deletes_old_hash(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes(b"v2")
    calls: list[tuple[str, str]] = []
    old_hash = hashlib.sha256(b"v1").hexdigest()
    name = _abs(tmp_path, "a.md")
    docs = {name: old_hash}  # server still has the old version
    client = _client(_server(docs, calls))
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()
    assert summary.replaced == 1 and summary.deleted == 1
    assert docs == {name: hashlib.sha256(b"v2").hexdigest()}  # old hash gone, new one in
    assert ("DELETE", f"/documents/{old_hash}") in calls


def test_sync_delete_removed_toggle(tmp_path: Path) -> None:
    gone_hash = hashlib.sha256(b"gone").hexdigest()
    managed = {"gone.md"}  # the agent previously tracked this file under its root

    # toggle OFF: the vanished file stays indexed
    calls: list[tuple[str, str]] = []
    docs = {"gone.md": gone_hash}
    client = _client(_server(docs, calls))
    try:
        summary = sync(client, str(tmp_path), {".md"}, delete_removed=False, managed=managed)
    finally:
        client.close()
    assert summary.deleted == 0 and docs == {"gone.md": gone_hash}

    # toggle ON: it's deleted from the index
    calls = []
    docs = {"gone.md": gone_hash}
    client = _client(_server(docs, calls))
    try:
        summary = sync(client, str(tmp_path), {".md"}, delete_removed=True, managed=managed)
    finally:
        client.close()
    assert summary.deleted == 1 and docs == {}


def test_sync_delete_removed_never_touches_unmanaged_docs(tmp_path: Path) -> None:
    """delete_removed must not delete tenant docs the agent never tracked (the over-delete bug)."""
    calls: list[tuple[str, str]] = []
    docs = {"other.md": "hother"}  # ingested by some other source; not under our root
    client = _client(_server(docs, calls))
    try:
        # managed is empty (we've never seen other.md) → nothing of ours to remove
        summary = sync(client, str(tmp_path), {".md"}, delete_removed=True, managed=set())
    finally:
        client.close()
    assert summary.deleted == 0
    assert docs == {"other.md": "hother"}  # untouched
    assert not any(m == "DELETE" for m, _ in calls)


def test_sync_multiple_folders_keep_same_name_distinct(tmp_path: Path) -> None:
    """Two watched folders that each contain notes.md stay two documents (absolute keys)."""
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    (a / "notes.md").write_bytes(b"from A")
    (b / "notes.md").write_bytes(b"from B")
    calls: list[tuple[str, str]] = []
    docs: dict[str, str] = {}
    client = _client(_server(docs, calls))
    try:
        summary = sync(client, [str(a), str(b)], {".md"})
    finally:
        client.close()
    assert summary.indexed == 2
    assert set(docs) == {_abs(a, "notes.md"), _abs(b, "notes.md")}  # both kept, no clash


def test_sync_add_only_when_documents_unsupported(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes(b"alpha")
    calls: list[tuple[str, str]] = []
    docs: dict[str, str] = {}
    client = _client(_server(docs, calls, supported=False))
    try:
        summary = sync(client, str(tmp_path), {".md"}, delete_removed=True)
    finally:
        client.close()
    # No /documents map → still ingests, but never tries to delete.
    assert summary.indexed == 1
    assert not any(m == "DELETE" for m, _ in calls)


# --------------------------------------------------------------------------- client methods


def test_client_documents_and_delete() -> None:
    calls: list[tuple[str, str]] = []
    docs = {"a.md": "h1"}
    client = _client(_server(docs, calls))
    try:
        supported, listing = client.documents()
        assert supported is True
        assert listing == [{"path": "a.md", "source_hash": "h1", "chunks": 1}]
        assert client.delete_document("h1") == 1
    finally:
        client.close()
    assert ("GET", "/documents") in calls
    assert ("DELETE", "/documents/h1") in calls
