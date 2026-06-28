"""The replace-aware sync engine — the brain the window, the CLI, and tests all share.

Given a watched root and the server's current document list, decide per file whether to
**ingest** (new), **skip** (byte-identical — content-hash dedup already covers it), **replace**
(same path, new content → ingest the new bytes then delete the stale hash), or **delete** (a
path that vanished on disk, only when ``delete_removed`` is on). Pure stdlib + ``SiftClient``;
never imports ``sift``.

Upload names are the file's path **relative to the watched root, normalised to POSIX** so the
same file maps to the same server ``path`` key on macOS, Windows, and Linux — which is what
makes path-based replacement deterministic across machines.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import PurePath

from agent.client import SiftClient

DEFAULT_INCLUDE = [".txt", ".md", ".pdf", ".docx", ".xlsx", ".pptx", ".html"]


def upload_name(root: str, full: str) -> str:
    """The stable, cross-platform upload key for ``full`` under ``root`` (POSIX relpath)."""
    return PurePath(os.path.relpath(full, root)).as_posix()


def abs_upload_name(full: str) -> str:
    """Absolute POSIX upload key — unique across *multiple* watched folders (no relpath clash)."""
    return PurePath(os.path.abspath(full)).as_posix()


def _iter_matching(root: str, includes: set[str]):
    """Yield absolute paths of files under ``root`` (a file or directory) matching ``includes``."""
    if os.path.isfile(root):
        if os.path.splitext(root)[1].lower() in includes:
            yield os.path.abspath(root)
        return
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = os.path.join(dirpath, name)
            if os.path.splitext(full)[1].lower() in includes:
                yield full


def collect(root: str, includes: set[str]) -> list[tuple[str, str, bytes]]:
    """Walk one ``root``; return ``(relpath_name, sha256_hex, data)`` — legacy one-shot keys."""
    name_root = (os.path.dirname(root) or ".") if os.path.isfile(root) else root
    found: list[tuple[str, str, bytes]] = []
    for full in _iter_matching(root, includes):
        with open(full, "rb") as fh:
            data = fh.read()
        found.append((upload_name(name_root, full), hashlib.sha256(data).hexdigest(), data))
    return found


def collect_roots(roots: list[str], includes: set[str]) -> list[tuple[str, str, bytes]]:
    """Walk every root; return ``(abs_name, sha256_hex, data)``, de-duped across overlapping roots.

    Absolute keys mean two watched folders that each contain ``notes.md`` stay distinct documents.
    """
    found: list[tuple[str, str, bytes]] = []
    seen: set[str] = set()
    for root in roots:
        for full in _iter_matching(root, includes):
            name = abs_upload_name(full)
            if name in seen:
                continue
            seen.add(name)
            with open(full, "rb") as fh:
                data = fh.read()
            found.append((name, hashlib.sha256(data).hexdigest(), data))
    return found


@dataclass(frozen=True, slots=True)
class Actions:
    """The reconcile verdict: which files to (re-)upload and which stale hashes to remove."""

    ingest: list[str] = field(default_factory=list)  # upload_names to send
    skip: list[str] = field(default_factory=list)  # identical, no upload
    replace: list[str] = field(default_factory=list)  # subset of ingest that supersede a doc
    delete_hashes: list[str] = field(default_factory=list)  # source_hashes to DELETE


@dataclass(frozen=True, slots=True)
class Summary:
    """Per-sync tallies for the UI status line, plus the paths now under management.

    ``managed`` is the set of upload-paths this sync saw on disk — feed it back into the next
    :func:`sync` call as ``managed=`` so ``delete_removed`` only ever removes files this agent
    actually tracked (never other documents that happen to share the tenant).
    """

    indexed: int = 0
    replaced: int = 0
    skipped: int = 0
    deleted: int = 0
    failed: int = 0
    error: str | None = None
    managed: frozenset[str] = frozenset()

    def line(self) -> str:
        if self.error:
            return f"error: {self.error}"
        return (
            f"{self.indexed} indexed · {self.replaced} replaced · "
            f"{self.deleted} deleted · {self.skipped} skipped · {self.failed} failed"
        )


def reconcile(
    local: dict[str, str],
    remote: dict[str, str],
    *,
    delete_removed: bool,
    managed: set[str] | None = None,
) -> Actions:
    """Diff local ``{path: content_hash}`` against remote ``{path: source_hash}``.

    - path not on the server → ingest
    - same hash → skip (byte-identical)
    - different hash → ingest the new bytes **and** delete the old hash (replace)
    - previously **managed** by this agent, now gone from disk, and ``delete_removed`` → delete

    ``managed`` scopes removal to paths this agent has tracked. ``None`` means "every remote
    path" — only safe for a single agent that owns the whole tenant; :func:`sync` always passes
    an explicit set so it never deletes documents another source ingested.
    """
    actions = Actions()
    for path, digest in local.items():
        prior = remote.get(path)
        if prior is None:
            actions.ingest.append(path)
        elif prior == digest:
            actions.skip.append(path)
        else:
            actions.ingest.append(path)
            actions.replace.append(path)
            actions.delete_hashes.append(prior)
    if delete_removed:
        candidates = set(remote) if managed is None else (managed & set(remote))
        for path in candidates:
            if path not in local:
                actions.delete_hashes.append(remote[path])
    return actions


def sync(
    client: SiftClient,
    roots: str | list[str],
    includes: set[str],
    *,
    tenant: str = "default",
    delete_removed: bool = False,
    managed: set[str] | None = None,
) -> Summary:
    """Run one full reconcile pass across one or more ``roots``: ingest new/changed, delete stale.

    ``roots`` is a folder/file path or a list of them (each indexed by absolute path, so files
    sharing a relative name across folders stay distinct). ``managed`` is the set of upload-paths
    the *previous* sync saw on disk (``Summary.managed``); with ``delete_removed`` on, only those
    are eligible for removal — so the agent never deletes documents another source ingested. The
    returned ``Summary.managed`` is this pass's on-disk set, to thread into the next call.

    Falls back to add-only if the store doesn't support listing documents (``supported=False``):
    replacement/removal need ``/documents``, so without it we can still ingest (the engine's
    content-hash dedup keeps identical files from re-embedding).
    """
    roots = [roots] if isinstance(roots, str) else list(roots)
    files = collect_roots(roots, includes)
    local = {name: digest for name, digest, _data in files}
    data_by_name = {name: data for name, _digest, data in files}
    now_managed = frozenset(local)

    try:
        supported, docs = client.documents()
    except Exception as exc:  # network/HTTP — surface it rather than half-syncing
        return Summary(error=str(exc), managed=now_managed)

    remote = {d["path"]: d["source_hash"] for d in docs} if supported else {}
    actions = reconcile(
        local,
        remote,
        delete_removed=delete_removed and supported,
        managed=(managed if managed is not None else set()),
    )

    indexed = replaced = deleted = failed = 0
    error: str | None = None

    if actions.ingest:
        payload = [(name, data_by_name[name]) for name in actions.ingest]
        try:
            resp = client.ingest(tenant, payload)
            replaced_set = set(actions.replace)
            for r in resp.get("results", []):
                if r.get("status") == "indexed":
                    indexed += 1
                    if r.get("path") in replaced_set:
                        replaced += 1
                elif r.get("status") == "failed":
                    failed += 1
        except Exception as exc:
            return Summary(skipped=len(actions.skip), error=str(exc), managed=now_managed)

    for source_hash in actions.delete_hashes:
        try:
            client.delete_document(source_hash)
            deleted += 1
        except Exception as exc:  # keep going; report the last error
            failed += 1
            error = str(exc)

    return Summary(
        indexed=indexed,
        replaced=replaced,
        skipped=len(actions.skip),
        deleted=deleted,
        failed=failed,
        error=error,
        managed=now_managed,
    )
