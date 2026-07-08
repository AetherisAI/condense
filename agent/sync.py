"""The replace-aware sync engine — the brain the window, the CLI, and tests all share.

Given a watched root and the server's current document list, decide per file whether to
**ingest** (new), **skip** (byte-identical — content-hash dedup already covers it), **replace**
(same path, new content → ingest the new bytes then delete the stale hash), or **delete** (a
path that vanished on disk, only when ``delete_removed`` is on). Pure stdlib + ``SiftClient``;
never imports ``sift``.

Upload names are the file's path **relative to the watched root, normalised to POSIX** so the
same file maps to the same server ``path`` key on macOS, Windows, and Linux — which is what
makes path-based replacement deterministic across machines. This is true for a **single**
watched root regardless of which collector built the key (:func:`collect` for one-shot,
:func:`collect_roots` for ``--watch``/the desktop app) — see DECISIONS.md D45: before D45,
:func:`collect_roots` keyed by *absolute* path while :func:`collect` keyed root-relative, so a
watch-mode reconcile against a one-shot-ingested corpus never matched anything and re-uploaded
(almost) the whole tree every restart. With **multiple** watched roots, each key is prefixed
with its root's basename (disambiguated on collision, see :func:`_root_prefixes`) so two roots
that each contain e.g. ``notes.md`` still map to two distinct, stable server paths.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import PurePath

from agent.client import PartialIngestError, SiftClient

# Default cap on a single file's size before it's skipped entirely (never hashed, never held in
# memory) — see DEFAULT_INCLUDE's note on OCR-fed images: a folder of large scans/exports could
# otherwise dominate a sync's memory footprint one file at a time. Overridable per call (agent.cli
# grows a matching flag; agent.config.AgentConfig gets a matching field for the desktop app).
DEFAULT_MAX_FILE_SIZE_MB = 100

# Streamed sha256 chunk size — large enough to be fast, small enough that hashing a multi-GB file
# never holds more than this much of it in memory at once (A3).
_HASH_CHUNK_BYTES = 1 << 20  # 1 MiB

# Text + office formats markitdown parses directly, plus image formats that carry text. Images
# (and scanned/text-less PDFs) only yield text when the server has OCR enabled (OCR_ENABLED +
# OCR_BASE_URL) — they're collected here so a screenshot dropped into a watched folder flows
# through to the OCR fallback automatically; with OCR off they simply produce no chunks.
DEFAULT_INCLUDE = [
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".html",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
]

# Directory *names* the walk never descends into — vendored/tooling trees that happen to sit
# under a watched folder and would otherwise get scanned for matching extensions (a real corpus
# audit found numpy/lxml license ``.txt``/``.md`` files under a nested ``.venv/site-packages``
# inflating the upload set with junk that isn't the user's own content). Matched against a bare
# directory *basename*, not a path — so it prunes a ``.venv`` wherever it appears in the tree, not
# just at the watched root. Overridable per call (``collect``/``collect_roots``/``sync``), via
# ``agent.config.AgentConfig.exclude_dirs`` (desktop app), and via ``agent.cli --exclude-dir``
# (headless one-shot/``--watch``) — see DECISIONS.md D35.
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        "site-packages",
    }
)

# Vendored package *metadata* directories carry a package-specific name (e.g.
# ``numpy-1.26.4.dist-info``), so they can't live in a fixed-name set — matched by suffix instead.
_EXCLUDE_DIR_SUFFIXES = (".dist-info", ".egg-info")


def _is_excluded_dir(name: str, exclude_dirs: frozenset[str] | set[str]) -> bool:
    """True if a directory named ``name`` should be pruned from the walk entirely.

    ANY directory whose basename starts with ``.`` is pruned unconditionally, on top of the
    named/suffix checks below — a real corpus ingested ``.session_memory/*.md`` junk that no
    fixed-name set could have anticipated (an agent/editor/tool's own hidden bookkeeping dir,
    not the user's content). This is on top of, never instead of, ``exclude_dirs`` — a caller's
    own additions (``agent.cli --exclude-dir``, ``AgentConfig.exclude_dirs``) still prune their
    named dirs exactly as before.
    """
    return name.startswith(".") or name in exclude_dirs or name.endswith(_EXCLUDE_DIR_SUFFIXES)


# Individual *filenames* (not directories — see DEFAULT_EXCLUDE_DIRS above) never matched even
# when their extension is in ``includes``: an agent's own bookkeeping files sitting inside a
# watched folder are not the user's content. Glob (``fnmatch``) patterns, matched against the
# bare basename — a real corpus audit found a stray ``MEMORY.md`` polluting an index (D39).
# Overridable per call (``collect``/``collect_roots``/``sync``), via
# ``agent.config.AgentConfig.exclude_files`` (desktop app), and via ``agent.cli --exclude-file``
# (headless one-shot/``--watch``) — same shape as ``DEFAULT_EXCLUDE_DIRS`` (D35).
DEFAULT_EXCLUDE_FILES: frozenset[str] = frozenset(
    {
        "MEMORY.md",
        "CLAUDE.md",
        "AGENTS.md",
        "*.tmp",
        ".*",
    }
)


def _is_excluded_file(name: str, exclude_files: frozenset[str] | set[str]) -> bool:
    """True if a file named ``name`` (bare basename) should never be matched/uploaded."""
    return any(fnmatch.fnmatch(name, pattern) for pattern in exclude_files)


def upload_name(root: str, full: str) -> str:
    """The stable, cross-platform upload key for ``full`` under ``root`` (POSIX relpath)."""
    return PurePath(os.path.relpath(full, root)).as_posix()


def _name_root(root: str) -> str:
    """The directory a file's upload-name relpath is computed against.

    A file ``root`` (as opposed to a directory) has no directory of its own to be relative to,
    so its key is computed relative to its *parent* — giving just the bare filename, same as
    :func:`collect` has always done. Shared by :func:`collect` and :func:`collect_roots` so both
    collectors agree on a single root's keys byte-for-byte (D45).
    """
    return (os.path.dirname(root) or ".") if os.path.isfile(root) else root


def _root_prefixes(roots: list[str]) -> dict[str, str | None]:
    """Per-root upload-key prefix: ``None`` for a lone root, else a disambiguated basename.

    A single watched root needs **no prefix at all** — that's what makes :func:`collect_roots`
    produce the exact same keys as one-shot :func:`collect` for the single-root case (D45), which
    is what lets ``--watch`` reconcile cleanly against a corpus ingested one-shot.

    With multiple roots, each file's key is prefixed with its root's basename so two roots that
    happen to share a relative name (e.g. two folders each containing ``notes.md``) still map to
    two distinct, stable documents. A basename collision *across roots* (e.g. two roots both
    named ``Acme``, nested under different parents) is disambiguated deterministically by
    suffixing ``-2``, ``-3``, … in the order ``roots`` was given — never dependent on set/dict
    iteration order, so the same ``roots`` list always yields the same prefixes.
    """
    if len(roots) <= 1:
        return dict.fromkeys(roots)
    counts: dict[str, int] = {}
    # Annotated with the declared return's value type (str | None): dict is invariant, so a bare
    # dict[str, str] is not assignable to the dict[str, str | None] return.
    prefixes: dict[str, str | None] = {}
    for root in roots:
        base = os.path.basename(os.path.normpath(root)) or root
        counts[base] = counts.get(base, 0) + 1
        prefixes[root] = base if counts[base] == 1 else f"{base}-{counts[base]}"
    return prefixes


def _iter_matching(
    root: str,
    includes: set[str],
    exclude_dirs: frozenset[str] | set[str] = DEFAULT_EXCLUDE_DIRS,
    exclude_files: frozenset[str] | set[str] = DEFAULT_EXCLUDE_FILES,
):
    """Yield absolute paths of files under ``root`` (a file or directory) matching ``includes``.

    Any subdirectory whose basename is excluded (see :data:`DEFAULT_EXCLUDE_DIRS`) is pruned
    from the walk entirely — its contents are never listed, hashed, or matched, however deep.
    Any filename matching an ``exclude_files`` glob (see :data:`DEFAULT_EXCLUDE_FILES`) is
    skipped even when its extension is otherwise included.
    """
    if os.path.isfile(root):
        name = os.path.basename(root)
        if os.path.splitext(root)[1].lower() in includes and not _is_excluded_file(
            name, exclude_files
        ):
            yield os.path.abspath(root)
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _is_excluded_dir(d, exclude_dirs)]
        for name in filenames:
            if _is_excluded_file(name, exclude_files):
                continue
            full = os.path.join(dirpath, name)
            if os.path.splitext(full)[1].lower() in includes:
                yield full


def _stat_sorted(fulls: Iterable[str]) -> list[tuple[str, os.stat_result]]:
    """Stat each path ONCE and return ``(full, stat)`` pairs oldest-modified first.

    Uploading a batch in mtime order makes the server stamp each document's ``indexed_at`` in
    modification order, so the most recently edited file in a near-duplicate set (e.g. v2 of a
    doc) carries the latest recency token and wins version-collapse at search time — even when
    every version is ingested in the same cold pass.

    A single ``os.stat`` yields both ``st_mtime`` (ordering + the modified-at stamp) and
    ``st_size`` (the size guard), so the collect loop reuses it instead of re-issuing up to four
    separate ``getmtime``/``getsize``/``exists`` syscalls per file. A file that vanished between
    listing and stat is dropped here (it could be neither hashed nor uploaded anyway).
    """
    stated: list[tuple[str, os.stat_result]] = []
    for full in fulls:
        try:
            stated.append((full, os.stat(full)))
        except OSError:
            continue
    stated.sort(key=lambda item: item[1].st_mtime)
    return stated


def _modified_iso(st: os.stat_result) -> str:
    """The file's last-modified time (from a prior :func:`os.stat`) as an ISO-8601 UTC string.

    ``last_modified`` (mtime), not creation time: editing v1 into v2 bumps v2's mtime, which is
    exactly "this is the newer version". It is also portable (Linux has no reliable birth time).
    """
    return datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat()


def _sha256_cached(
    full: str, st: os.stat_result, cache: dict[str, tuple[int, int, str]] | None
) -> str:
    """SHA-256 of ``full``, reusing a cached digest while ``(mtime_ns, size)`` is unchanged.

    Watch mode re-collects the whole tree on every debounced change, so without a cache a single
    edit re-reads and re-hashes the entire corpus. Keyed by absolute path → ``(st_mtime_ns,
    st_size, sha)`` and bounded to one entry per path (self-updating on edit): any real edit bumps
    mtime/size and misses the cache, preserving content-hash dedup correctness. ``cache is None``
    (one-shot ingest, tests) always hashes fresh — identical behaviour to before this cache.
    """
    if cache is None:
        return _sha256_file(full)
    key = os.path.abspath(full)
    entry = cache.get(key)
    if entry is not None and entry[0] == st.st_mtime_ns and entry[1] == st.st_size:
        return entry[2]
    sha = _sha256_file(full)
    cache[key] = (st.st_mtime_ns, st.st_size, sha)
    return sha


def _sha256_file(path: str) -> str:
    """Stream ``path`` through SHA-256 in fixed-size chunks — never holds the whole file at once.

    This is what makes cataloguing a folder full of large files (images for OCR, big PDFs, …)
    memory-bounded: a file's full contents used to be read into a Python ``bytes`` object just to
    compute its digest and sit in the returned list until upload (A3).
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_BYTES), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_file(path: str) -> Callable[[], bytes]:
    """A zero-arg loader that reads ``path`` fully only when called.

    Used so a whole tree's worth of files can be catalogued (name/hash/mtime) without ever
    holding more than one upload batch's bytes in memory at a time — the loader is handed to
    :meth:`agent.client.SiftClient.ingest`, which calls it only while building that file's batch.
    """

    def _load() -> bytes:
        with open(path, "rb") as fh:
            return fh.read()

    return _load


def _skip_oversized(full: str, st: os.stat_result, max_bytes: int, max_file_size_mb: int) -> bool:
    """True (and warns) if ``full`` (already stat'd) exceeds the size guard — caller skips it."""
    if st.st_size <= max_bytes:
        return False
    warnings.warn(
        f"agent: skipping {full} ({st.st_size} bytes exceeds max_file_size_mb={max_file_size_mb})",
        stacklevel=3,
    )
    return True


def collect(
    root: str,
    includes: set[str],
    *,
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
    exclude_dirs: frozenset[str] | set[str] = DEFAULT_EXCLUDE_DIRS,
    exclude_files: frozenset[str] | set[str] = DEFAULT_EXCLUDE_FILES,
    hash_cache: dict[str, tuple[int, int, str]] | None = None,
) -> list[tuple[str, str, Callable[[], bytes], str]]:
    """Walk one ``root`` → ``(relpath_name, sha256_hex, loader, modified_at)`` (one-shot keys).

    ``loader`` is a zero-arg callable that reads the file's bytes on demand; the digest itself is
    computed by streaming the file, so no matched file's full contents are held in memory just to
    catalogue it (A3). A file larger than ``max_file_size_mb`` is skipped entirely (with a
    ``UserWarning``) — never hashed, never loaded. Any directory named in ``exclude_dirs`` (default
    :data:`DEFAULT_EXCLUDE_DIRS`) is pruned from the walk before it's ever listed (D35); any
    filename matching ``exclude_files`` (default :data:`DEFAULT_EXCLUDE_FILES`) is skipped the
    same way, even when its extension is otherwise included (D39). ``hash_cache`` (owned by a
    long-lived watch caller) skips re-hashing files whose mtime/size are unchanged (see
    :func:`_sha256_cached`); ``None`` hashes every file fresh.
    """
    max_bytes = max_file_size_mb * 1024 * 1024
    name_root = _name_root(root)
    found: list[tuple[str, str, Callable[[], bytes], str]] = []
    for full, st in _stat_sorted(_iter_matching(root, includes, exclude_dirs, exclude_files)):
        if _skip_oversized(full, st, max_bytes, max_file_size_mb):
            continue
        sha = _sha256_cached(full, st, hash_cache)
        found.append((upload_name(name_root, full), sha, _read_file(full), _modified_iso(st)))
    return found


def collect_roots(
    roots: list[str],
    includes: set[str],
    *,
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
    exclude_dirs: frozenset[str] | set[str] = DEFAULT_EXCLUDE_DIRS,
    exclude_files: frozenset[str] | set[str] = DEFAULT_EXCLUDE_FILES,
    hash_cache: dict[str, tuple[int, int, str]] | None = None,
) -> list[tuple[str, str, Callable[[], bytes], str]]:
    """Walk every root; return ``(name, sha256_hex, loader, modified_at)``, de-duped across roots.

    **Keying (D45):** for a single root, the key is root-relative POSIX — byte-for-byte the same
    key :func:`collect` would produce for that same root, which is what lets a ``--watch``
    reconcile match a corpus ingested one-shot instead of re-uploading it every restart. For
    *multiple* roots, each key is prefixed with its root's (disambiguated) basename — see
    :func:`_root_prefixes` — so two roots that happen to share a relative name still stay two
    distinct documents.

    A file reached through more than one declared root (overlapping/nested roots) is only
    catalogued once, under whichever root visits it first — de-duped by its *resolved* physical
    path, not by upload key (two different roots can legitimately produce two different keys for
    the same bytes; only literally re-visiting the same file is deduped).

    Ordered oldest-modified first (see :func:`_stat_sorted`) so recency survives into the index.
    ``loader``, the size guard, ``exclude_dirs``, and ``exclude_files`` behave exactly as in
    :func:`collect` (A3/D35/D39).
    """
    max_bytes = max_file_size_mb * 1024 * 1024
    prefixes = _root_prefixes(roots)
    seen_physical: set[str] = set()  # resolved abs path → already catalogued (overlapping roots)
    by_full: dict[str, str] = {}  # full path → its upload key, first root to visit it wins
    for root in roots:
        name_root = _name_root(root)
        prefix = prefixes.get(root)
        for full in _iter_matching(root, includes, exclude_dirs, exclude_files):
            resolved = os.path.abspath(full)
            if resolved in seen_physical:
                continue
            seen_physical.add(resolved)
            rel = upload_name(name_root, full)
            by_full[full] = f"{prefix}/{rel}" if prefix else rel
    found: list[tuple[str, str, Callable[[], bytes], str]] = []
    for full, st in _stat_sorted(by_full):
        if _skip_oversized(full, st, max_bytes, max_file_size_mb):
            continue
        sha = _sha256_cached(full, st, hash_cache)
        found.append((by_full[full], sha, _read_file(full), _modified_iso(st)))
    return found


@dataclass(frozen=True, slots=True)
class Actions:
    """The reconcile verdict: which files to (re-)upload and which stale hashes to remove."""

    ingest: list[str] = field(default_factory=list)  # upload_names to send
    skip: list[str] = field(default_factory=list)  # identical, no upload
    replace: list[str] = field(default_factory=list)  # subset of ingest that supersede a doc
    delete_hashes: list[str] = field(default_factory=list)  # source_hashes to DELETE


@dataclass(frozen=True, slots=True)
class Failure:
    """One file the server reported as ``"failed"``: its upload path and the server's detail.

    Surfaced so a caller (``agent.cli --json``, the desktop app) can name the file rather than
    just counting it — see :data:`Summary.failures`.
    """

    path: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Summary:
    """Per-sync tallies for the UI status line, plus the paths now under management.

    ``managed`` is the set of upload-paths this sync saw on disk — feed it back into the next
    :func:`sync` call as ``managed=`` so ``delete_removed`` only ever removes files this agent
    actually tracked (never other documents that happen to share the tenant).

    ``skipped`` is **truthful** (D45): it counts both a client-side skip (reconcile decided the
    path's hash already matches remote, so the file was never even uploaded) AND a server-side
    ``skipped_dedup`` result (the file WAS uploaded — reconcile thought it was new/changed — but
    the engine's own content-hash dedup recognised the bytes and skipped re-embedding). Before
    D45, only the client-side count was tallied, so a path-keying mismatch that forced every file
    through the upload path (server dedup catching it every time) still reported ``0 skipped`` —
    a misleading zero that hid exactly the bandwidth/round-trip waste it should have surfaced.

    ``failures`` names every file counted in ``failed`` that came from a server-reported ingest
    result (path + the server's ``detail`` string) — before this, a watch-mode "2 failed" line
    gave no way to tell *which* two files without digging through server logs (the corrupt-xlsx
    gap, see DECISIONS.md D52/D54). A failure folded in from the delete-stale-hash pass below
    (keyed by content hash, not a watched path) is counted in ``failed`` but has no natural path
    to report, so it is *not* added here — a known, narrow gap, not a silent one.
    """

    indexed: int = 0
    replaced: int = 0
    skipped: int = 0
    deleted: int = 0
    failed: int = 0
    error: str | None = None
    managed: frozenset[str] = frozenset()
    failures: tuple[Failure, ...] = ()

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

    **Ordering invariant** (relied on by :func:`sync` for partial-batch accounting, A4):
    ``actions.delete_hashes[:len(actions.replace)]`` is exactly the old hash for each path in
    ``actions.replace``, **in the same order** — every ``replace.append(path)`` above is
    immediately followed by the matching ``delete_hashes.append(prior)``. Any further entries
    (appended by the ``delete_removed`` pass) come after and aren't tied to an upload.
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
    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB,
    exclude_dirs: frozenset[str] | set[str] = DEFAULT_EXCLUDE_DIRS,
    exclude_files: frozenset[str] | set[str] = DEFAULT_EXCLUDE_FILES,
    hash_cache: dict[str, tuple[int, int, str]] | None = None,
) -> Summary:
    """Run one full reconcile pass across one or more ``roots``: ingest new/changed, delete stale.

    ``roots`` is a folder/file path or a list of them (each indexed by absolute path, so files
    sharing a relative name across folders stay distinct). ``managed`` is the set of upload-paths
    the *previous* sync saw on disk (``Summary.managed``); with ``delete_removed`` on, only those
    are eligible for removal — so the agent never deletes documents another source ingested. The
    returned ``Summary.managed`` is this pass's on-disk set, to thread into the next call.
    ``max_file_size_mb``, ``exclude_dirs``, and ``exclude_files`` are the per-file size guard,
    vendored-dir pruning, and junk-filename pruning passed through to :func:`collect_roots`
    (A3/D35/D39).

    Falls back to add-only if the store doesn't support listing documents (``supported=False``):
    replacement/removal need ``/documents``, so without it we can still ingest (the engine's
    content-hash dedup keeps identical files from re-embedding).

    **Partial-batch accounting (A4):** if :meth:`SiftClient.ingest` raises
    :class:`~agent.client.PartialIngestError` (a later batch failed after earlier ones landed),
    the earlier batches' indexed/replaced counts are still credited and ``Summary.error`` reports
    the failure — a mid-run failure no longer discards already-confirmed progress. A *replaced*
    document's stale hash is only deleted once its replacement is confirmed ``"indexed"`` in the
    results actually received (whether from a full success or a partial one); an unconfirmed
    replacement leaves the old hash in place, so the next ``sync()`` call sees local still differs
    from remote and retries — no lost update, no premature delete.
    """
    roots = [roots] if isinstance(roots, str) else list(roots)
    files = collect_roots(
        roots,
        includes,
        max_file_size_mb=max_file_size_mb,
        exclude_dirs=exclude_dirs,
        exclude_files=exclude_files,
        hash_cache=hash_cache,
    )
    local = {name: digest for name, digest, _loader, _m in files}
    loader_by_name = {name: loader for name, _digest, loader, _m in files}
    mtime_by_name = {name: modified for name, _digest, _loader, modified in files}
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

    indexed = replaced = deleted = failed = skipped_dedup = 0
    error: str | None = None
    indexed_paths: set[str] = set()
    failures: list[Failure] = []

    if actions.ingest:
        payload = [(name, loader_by_name[name]) for name in actions.ingest]
        mtimes = {name: mtime_by_name[name] for name in actions.ingest}
        replaced_set = set(actions.replace)
        try:
            resp = client.ingest(tenant, payload, modified_at=mtimes)
        except PartialIngestError as exc:
            # One or more batches landed before the failure — credit them (A4) instead of
            # discarding all progress; the failure is still surfaced via ``error`` below.
            resp = exc.partial
            error = str(exc)
        except Exception as exc:
            return Summary(skipped=len(actions.skip), error=str(exc), managed=now_managed)

        for r in resp.get("results", []):
            path, status = r.get("path"), r.get("status")
            if status == "indexed":
                indexed += 1
                indexed_paths.add(path)
                if path in replaced_set:
                    replaced += 1
            elif status == "failed":
                failed += 1
                failures.append(Failure(path=path, error=r.get("detail")))
            elif status == "skipped_dedup":
                # The engine's own content-hash dedup caught a file reconcile() thought was
                # new/changed (D45) — not lost, not an error, just wasted bandwidth; tallied into
                # the truthful ``skipped`` total below rather than silently dropped.
                skipped_dedup += 1

    # Only remove a replaced document's stale hash once its replacement is *confirmed* indexed —
    # never on a batch exception, and never on a per-file "failed" status inside an otherwise-200
    # response. A hash from ``delete_removed`` (a file that vanished from disk) isn't tied to any
    # upload, so it's always eligible. Relies on reconcile()'s ordering invariant (see its
    # docstring): the first len(actions.replace) delete_hashes line up with actions.replace.
    n_replace = len(actions.replace)
    replace_hashes = actions.delete_hashes[:n_replace]
    extra_hashes = actions.delete_hashes[n_replace:]
    to_delete = list(extra_hashes)
    to_delete += [
        h for path, h in zip(actions.replace, replace_hashes, strict=True) if path in indexed_paths
    ]

    for source_hash in to_delete:
        try:
            client.delete_document(source_hash)
            deleted += 1
        except Exception as exc:  # keep going; fold in rather than overwrite an ingest error
            failed += 1
            error = f"{error}; {exc}" if error else str(exc)

    return Summary(
        indexed=indexed,
        replaced=replaced,
        skipped=len(actions.skip) + skipped_dedup,
        deleted=deleted,
        failed=failed,
        error=error,
        managed=now_managed,
        failures=tuple(failures),
    )
