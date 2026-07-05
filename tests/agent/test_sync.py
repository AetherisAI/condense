"""Offline tests for the replace-aware sync engine — ``httpx.MockTransport``, no live server.

A stub server backs ``GET /documents``, ``POST /ingest``, and ``DELETE /documents/{hash}`` from
an in-memory ``{path: source_hash}`` map, recording every request so the tests can assert the
*exact* add/replace/skip/delete behaviour (and that identical files never re-upload).
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("httpx")

import httpx  # noqa: E402
from agent.client import SiftClient  # noqa: E402
from agent.sync import collect, collect_roots, reconcile, sync  # noqa: E402

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


# --------------------------------------------------------------------------- collect / reconcile


def test_collect_normalises_to_posix(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.txt").write_bytes(b"charlie")
    names = {name for name, _h, _d, _m in collect(str(tmp_path), {".txt"})}
    assert names == {"sub/c.txt"}  # forward slash regardless of OS


def test_collect_roots_single_root_matches_collect_keys(tmp_path: Path) -> None:
    """The core D45 contract: for exactly ONE watched root, :func:`collect_roots` must produce
    the IDENTICAL set of upload keys as one-shot :func:`collect` — root-relative POSIX, no
    prefix. This is what lets a ``--watch`` reconcile match a corpus ingested one-shot instead of
    treating every file as new and re-uploading it (the live bug, see the ``sync()``-level repro
    below).
    """
    (tmp_path / "top.md").write_bytes(b"top")
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    (sub / "nested.md").write_bytes(b"nested")

    one_shot_names = {name for name, _h, _d, _m in collect(str(tmp_path), {".md"})}
    watch_names = {name for name, _h, _d, _m in collect_roots([str(tmp_path)], {".md"})}
    assert watch_names == one_shot_names == {"top.md", "sub/deep/nested.md"}


def test_collect_roots_multi_root_prefixes_with_basename(tmp_path: Path) -> None:
    """With more than one root, each key is prefixed with its OWN root's basename."""
    a = tmp_path / "Alpha"
    b = tmp_path / "Beta"
    a.mkdir()
    b.mkdir()
    (a / "x.md").write_bytes(b"a")
    (b / "y.md").write_bytes(b"b")

    names = {name for name, _h, _d, _m in collect_roots([str(a), str(b)], {".md"})}
    assert names == {"Alpha/x.md", "Beta/y.md"}


def test_collect_roots_disambiguates_basename_collisions_deterministically(tmp_path: Path) -> None:
    """Two roots that happen to share a basename (e.g. two folders both literally named
    ``Acme``, nested under different parents) get deterministic ``-2``, ``-3``, … suffixes, in
    the order the roots were given — never dependent on set/dict iteration order, so swapping the
    root order flips *which* root gets the bare prefix but is still fully deterministic.
    """
    p1 = tmp_path / "parent1" / "Acme"
    p2 = tmp_path / "parent2" / "Acme"
    p1.mkdir(parents=True)
    p2.mkdir(parents=True)
    (p1 / "notes.md").write_bytes(b"one")
    (p2 / "notes.md").write_bytes(b"two")

    forward = {name: digest for name, digest, _l, _m in collect_roots([str(p1), str(p2)], {".md"})}
    assert forward == {
        "Acme/notes.md": hashlib.sha256(b"one").hexdigest(),
        "Acme-2/notes.md": hashlib.sha256(b"two").hexdigest(),
    }

    reversed_ = {
        name: digest for name, digest, _l, _m in collect_roots([str(p2), str(p1)], {".md"})
    }
    assert reversed_ == {
        "Acme/notes.md": hashlib.sha256(b"two").hexdigest(),  # p2 listed first now
        "Acme-2/notes.md": hashlib.sha256(b"one").hexdigest(),
    }


def test_collect_roots_orders_oldest_modified_first(tmp_path: Path) -> None:
    # Upload order must follow mtime so the server stamps the newest version with the latest
    # recency token (it wins version-collapse at search time). Create out of order on purpose.
    (tmp_path / "v2.md").write_bytes(b"newer")
    (tmp_path / "v1.md").write_bytes(b"older")
    os.utime(tmp_path / "v1.md", (1000, 1000))  # older
    os.utime(tmp_path / "v2.md", (2000, 2000))  # newer

    order = [name for name, _h, _d, _m in collect_roots([str(tmp_path)], {".md"})]
    assert order.index("v1.md") < order.index("v2.md")


def test_collect_roots_skips_oversized_file_and_warns(tmp_path: Path) -> None:
    """The per-file size guard applies to the multi-root walk too (A3)."""
    (tmp_path / "small.md").write_bytes(b"tiny")
    (tmp_path / "big.md").write_bytes(b"x" * (2 * 1024 * 1024))  # 2 MiB

    with pytest.warns(UserWarning, match="big.md"):
        got = collect_roots([str(tmp_path)], {".md"}, max_file_size_mb=1)

    names = {name for name, _h, _d, _m in got}
    assert "small.md" in names
    assert "big.md" not in names


def test_collect_roots_prunes_vendored_directories_by_default(tmp_path: Path) -> None:
    """``--watch``'s continuous walk (:func:`collect_roots`) must skip vendored/tooling trees the
    same way the one-shot :func:`collect` does (R4/D35) — a nested ``.venv`` shouldn't resurrect
    junk matches just because the sync engine uses the multi-root code path.
    """
    (tmp_path / "real.md").write_bytes(b"keep me")
    venv = tmp_path / ".venv" / "lib" / "site-packages"
    venv.mkdir(parents=True)
    (venv / "NOTICE.md").write_bytes(b"vendored junk")

    got = collect_roots([str(tmp_path)], {".md"})

    names = {name for name, _h, _d, _m in got}
    assert "real.md" in names
    assert not any("site-packages" in n for n in names)


# ------------------------------------------------------------- live repro (D45): one-shot manifest


def test_reconcile_against_one_shot_manifest_skips_all_client_side(tmp_path: Path) -> None:
    """The exact live repro (D45): a corpus previously ingested ONE-SHOT (root-relative keys, via
    :func:`collect`) must be recognised as fully up to date by a ``--watch`` reconcile — 50 known
    files, 0 uploads. Before D45, :func:`collect_roots` keyed by *absolute* path while the
    server's remote map (built from a one-shot :func:`collect` ingest) was root-relative, so
    ``remote.get(path)`` never matched and every file looked "new" — every restart re-uploaded
    (almost) the whole corpus, caught pre-parse only by the server's own content-hash dedup.
    """
    n = 50
    for i in range(n):
        (tmp_path / f"doc-{i:02d}.md").write_bytes(f"content-{i}".encode())

    one_shot = collect(str(tmp_path), {".md"})
    remote = {name: digest for name, digest, _loader, _m in one_shot}
    assert len(remote) == n

    watch_files = collect_roots([str(tmp_path)], {".md"})
    local = {name: digest for name, digest, _loader, _m in watch_files}

    actions = reconcile(local, remote, delete_removed=False)
    assert actions.ingest == []
    assert len(actions.skip) == n


def test_sync_against_one_shot_manifest_uploads_nothing(tmp_path: Path) -> None:
    """Same repro, end-to-end through :func:`sync`: no ``POST /ingest`` at all, 50 skipped."""
    n = 50
    for i in range(n):
        (tmp_path / f"doc-{i:02d}.md").write_bytes(f"content-{i}".encode())
    one_shot = collect(str(tmp_path), {".md"})
    docs = {name: digest for name, digest, _loader, _m in one_shot}
    calls: list[tuple[str, str]] = []
    client = _client(_server(docs, calls))
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()
    assert summary.skipped == n
    assert summary.indexed == 0
    assert not any(m == "POST" and p == "/ingest" for m, p in calls)


def test_default_include_collects_images_for_ocr(tmp_path: Path) -> None:
    # Screenshots / scans must be picked up by the default include set so they reach the
    # server's OCR fallback; before this they were silently filtered out of folder watches.
    from agent.sync import DEFAULT_INCLUDE

    (tmp_path / "shot.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "scan.jpg").write_bytes(b"\xff\xd8 fake")
    (tmp_path / "notes.md").write_bytes(b"text")
    names = {name for name, _h, _d, _m in collect(str(tmp_path), set(DEFAULT_INCLUDE))}
    assert {"shot.png", "scan.jpg", "notes.md"} <= names


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
    assert docs == {"a.md": hashlib.sha256(b"alpha").hexdigest()}


def test_sync_skips_identical_without_upload(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes(b"alpha")
    calls: list[tuple[str, str]] = []
    docs = {"a.md": hashlib.sha256(b"alpha").hexdigest()}
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
    name = "a.md"
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


def test_sync_delete_removed_matches_new_relative_keys_across_two_passes(tmp_path: Path) -> None:
    """Regression (D45): the ``managed`` set and reconcile's delete-pass keying must use the SAME
    upload keys :func:`collect_roots` now produces (root-relative, not absolute) — otherwise a
    file that vanishes from disk would never be recognised as "managed and gone" and
    ``delete_removed`` would silently do nothing. The actual removal is still a hash-keyed DELETE
    on the server side, independent of any local key scheme — asserted here explicitly so a
    future keying change can't quietly break this without a test noticing.
    """
    (tmp_path / "keep.md").write_bytes(b"keep me")
    (tmp_path / "gone.md").write_bytes(b"delete me")
    calls: list[tuple[str, str]] = []
    docs: dict[str, str] = {}
    client = _client(_server(docs, calls))
    try:
        first = sync(client, [str(tmp_path)], {".md"}, delete_removed=True, managed=set())
        assert first.indexed == 2
        assert set(docs) == {"keep.md", "gone.md"}  # relative keys, matching one-shot collect()
        gone_hash = docs["gone.md"]

        os.remove(tmp_path / "gone.md")
        calls.clear()
        second = sync(
            client, [str(tmp_path)], {".md"}, delete_removed=True, managed=set(first.managed)
        )
    finally:
        client.close()

    assert second.deleted == 1
    assert docs == {"keep.md": hashlib.sha256(b"keep me").hexdigest()}
    assert ("DELETE", f"/documents/{gone_hash}") in calls  # deleted by content hash, as always


def test_sync_delete_removed_works_across_multiple_roots_with_prefixed_keys(tmp_path: Path) -> None:
    """Same regression, exercised with the multi-root, basename-prefixed key scheme."""
    a = tmp_path / "A"
    b = tmp_path / "B"
    a.mkdir()
    b.mkdir()
    (a / "x.md").write_bytes(b"from A")
    (b / "x.md").write_bytes(b"from B")
    calls: list[tuple[str, str]] = []
    docs: dict[str, str] = {}
    client = _client(_server(docs, calls))
    try:
        first = sync(client, [str(a), str(b)], {".md"}, delete_removed=True, managed=set())
        assert first.indexed == 2
        assert set(docs) == {"A/x.md", "B/x.md"}
        b_hash = docs["B/x.md"]

        os.remove(b / "x.md")
        second = sync(
            client, [str(a), str(b)], {".md"}, delete_removed=True, managed=set(first.managed)
        )
    finally:
        client.close()

    assert second.deleted == 1
    assert docs == {"A/x.md": hashlib.sha256(b"from A").hexdigest()}
    assert ("DELETE", f"/documents/{b_hash}") in calls


def test_sync_multiple_folders_keep_same_name_distinct(tmp_path: Path) -> None:
    """Two watched folders that each contain notes.md stay two documents (basename-prefixed keys,
    D45 — no longer absolute paths, see :func:`agent.sync._root_prefixes`).
    """
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
    assert set(docs) == {"A/notes.md", "B/notes.md"}  # both kept, no clash


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


# --------------------------------------------------------------------------- partial-batch (A4)


def test_sync_keeps_old_hash_when_replace_reports_per_file_failed(tmp_path: Path) -> None:
    """A per-file 'failed' status inside an otherwise-200 batch must not delete the old hash.

    Deleting on any non-exception ingest response (regardless of that file's own status) was the
    latent half of A4: the replacement never actually landed, so the old (still-valid) version
    must stay indexed.
    """
    (tmp_path / "a.md").write_bytes(b"v2")
    calls: list[tuple[str, str]] = []
    old_hash = hashlib.sha256(b"v1").hexdigest()
    name = "a.md"
    docs = {name: old_hash}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append((request.method, path))
        if request.method == "GET" and path == "/documents":
            documents = [{"path": p, "source_hash": h, "chunks": 1} for p, h in docs.items()]
            return httpx.Response(
                200, json={"tenant": "default", "documents": documents, "supported": True}
            )
        if request.method == "POST" and path == "/ingest":
            return httpx.Response(
                200, json={"tenant": "default", "results": [{"path": name, "status": "failed"}]}
            )
        return httpx.Response(404, json={"detail": "not found"})

    client = _client(handler)
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()

    assert summary.failed == 1
    assert summary.replaced == 0
    assert summary.deleted == 0  # old hash preserved — the replacement never actually landed
    assert docs == {name: old_hash}
    assert not any(m == "DELETE" for m, _ in calls)


def test_sync_mid_batch_failure_keeps_earlier_counts_and_safe_deletes(tmp_path: Path) -> None:
    """Batch 2 of an ingest 500s; batch 1's counts must survive and only its confirmed
    replacements get their stale hash cleaned up (A4 / DECISIONS D32).
    """
    for i, name in enumerate(["a.md", "b.md", "c.md", "d.md"]):
        (tmp_path / name).write_bytes(f"new-{name}".encode())
        os.utime(tmp_path / name, (1000 + i, 1000 + i))  # controls batch order (mtime-sorted)

    a_old = hashlib.sha256(b"old-a").hexdigest()
    b_old = hashlib.sha256(b"old-b").hexdigest()
    docs = {
        "a.md": a_old,
        "b.md": b_old,
    }  # c.md/d.md are brand new; a.md/b.md are replacements

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/documents":
            documents = [{"path": p, "source_hash": h, "chunks": 1} for p, h in docs.items()]
            return httpx.Response(
                200, json={"tenant": "default", "documents": documents, "supported": True}
            )
        if request.method == "POST" and path == "/ingest":
            names_data = _parse_multipart(request.content)
            names = {n for n, _ in names_data}
            new_names = {"c.md", "d.md"}
            if names & new_names:  # batch 2 (mtime-sorted after a/b) fails outright
                return httpx.Response(500, json={"detail": "boom"})
            results = []
            for pname, data in names_data:
                docs[pname] = hashlib.sha256(data).hexdigest()
                results.append({"path": pname, "status": "indexed"})
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

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler), batch_size=2)
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()

    assert summary.indexed == 2  # a.md, b.md landed in batch 1
    assert summary.replaced == 2
    assert summary.error is not None  # batch 2's failure is surfaced, not swallowed
    assert summary.deleted == 2  # both confirmed replacements' stale hashes cleaned up
    assert docs["a.md"] == hashlib.sha256(b"new-a.md").hexdigest()
    assert docs["b.md"] == hashlib.sha256(b"new-b.md").hexdigest()
    assert a_old not in docs.values()
    assert b_old not in docs.values()


def test_sync_retry_after_full_batch_failure_is_dedup_safe(tmp_path: Path) -> None:
    """After a batch fails outright (no partial progress), a retry finishes cleanly: no lost
    update, no premature/duplicate delete.
    """
    (tmp_path / "a.md").write_bytes(b"v2")
    old_hash = hashlib.sha256(b"v1").hexdigest()
    name = "a.md"
    docs = {name: old_hash}
    attempt = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/documents":
            documents = [{"path": p, "source_hash": h, "chunks": 1} for p, h in docs.items()]
            return httpx.Response(
                200, json={"tenant": "default", "documents": documents, "supported": True}
            )
        if request.method == "POST" and path == "/ingest":
            attempt["n"] += 1
            if attempt["n"] == 1:
                return httpx.Response(500, json={"detail": "boom"})
            results = []
            for pname, data in _parse_multipart(request.content):
                docs[pname] = hashlib.sha256(data).hexdigest()
                results.append({"path": pname, "status": "indexed"})
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

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler))
    try:
        first = sync(client, [str(tmp_path)], {".md"})
        assert first.error is not None
        assert first.deleted == 0  # nothing landed — old hash must not be touched
        assert docs == {name: old_hash}

        second = sync(client, [str(tmp_path)], {".md"})
        assert second.error is None
        assert second.replaced == 1
        assert second.deleted == 1
        assert docs == {name: hashlib.sha256(b"v2").hexdigest()}
    finally:
        client.close()


# ------------------------------------------------------------------- truthful counters (D45)


def test_sync_tallies_server_side_skipped_dedup_into_summary(tmp_path: Path) -> None:
    """A server-side ``skipped_dedup`` ingest result (the engine's own content-hash dedup
    catching a file :func:`reconcile` thought was new/changed) must be tallied into
    ``Summary.skipped`` — not silently dropped. Before D45 only the client-side
    ``len(actions.skip)`` was counted, so a path-keying mismatch that forced every file through
    the upload path still reported ``0 skipped``, hiding exactly the waste it should surface.
    """
    (tmp_path / "a.md").write_bytes(b"alpha")
    (tmp_path / "b.md").write_bytes(b"beta")
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append((request.method, path))
        if request.method == "GET" and path == "/documents":
            return httpx.Response(
                200, json={"tenant": "default", "documents": [], "supported": True}
            )
        if request.method == "POST" and path == "/ingest":
            results = [
                {"path": "a.md", "status": "indexed"},
                {"path": "b.md", "status": "skipped_dedup"},
            ]
            return httpx.Response(200, json={"tenant": "default", "results": results})
        return httpx.Response(404, json={"detail": "not found"})

    client = _client(handler)
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()

    assert summary.indexed == 1
    assert summary.skipped == 1  # b.md's skipped_dedup, tallied truthfully
    assert summary.failed == 0


def test_sync_tallies_skipped_dedup_within_partial_batch_failure(tmp_path: Path) -> None:
    """``skipped_dedup`` accounting must also flow through a PARTIAL (mid-batch failure)
    response, not just a fully successful ingest — PARTIAL reuses the exact same results list.
    """
    for i, name in enumerate(["a.md", "b.md", "c.md"]):
        (tmp_path / name).write_bytes(f"data-{name}".encode())
        os.utime(tmp_path / name, (1000 + i, 1000 + i))  # controls batch order (mtime-sorted)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/documents":
            return httpx.Response(
                200, json={"tenant": "default", "documents": [], "supported": True}
            )
        if request.method == "POST" and path == "/ingest":
            names_data = _parse_multipart(request.content)
            names = {n for n, _ in names_data}
            if "c.md" in names:  # batch 2 (mtime-sorted last) fails outright
                return httpx.Response(500, json={"detail": "boom"})
            results = [
                {"path": "a.md", "status": "indexed"},
                {"path": "b.md", "status": "skipped_dedup"},
            ]
            return httpx.Response(200, json={"tenant": "default", "results": results})
        return httpx.Response(404, json={"detail": "not found"})

    client = SiftClient(BASE_URL, TOKEN, transport=httpx.MockTransport(handler), batch_size=2)
    try:
        summary = sync(client, [str(tmp_path)], {".md"})
    finally:
        client.close()

    assert summary.indexed == 1
    assert summary.skipped == 1  # b.md's skipped_dedup, credited despite the later batch failure
    assert summary.error is not None


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
