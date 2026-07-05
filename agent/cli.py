"""The ``agent`` command line: walk a folder, diff against the manifest, upload the rest.

Two modes:

* **one-shot** (default) — collect, diff against ``/ingest/manifest``, upload new files, exit.
  Deliberately the same content hash the server stamps, computed here without importing ``sift``.
* **--watch** — run the continuous, replace-aware :func:`agent.sync.sync` engine on every change
  (the headless twin of the desktop app), optionally deleting docs whose files leave disk.

A one-shot upload that fails **after** at least one batch already landed
(:class:`~agent.client.PartialIngestError`) prints every per-file status the server actually
confirmed, then a ``PARTIAL: …`` summary line naming how many files never got attempted, and
exits non-zero — so a partial ingest can never look like either a silent success or a total
failure from the caller's shell.

``main`` takes an optional ``client`` so tests can inject a :class:`~agent.client.SiftClient`
built on an ``httpx.MockTransport`` and run the whole flow offline.
"""

from __future__ import annotations

import argparse
import os
import threading

from agent.client import PartialIngestError, SiftClient

# Re-exported from the shared sync engine so there's a single source of truth (and so existing
# imports ``from agent.cli import collect`` keep working).
from agent.sync import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_FILES,
    DEFAULT_INCLUDE,
    DEFAULT_MAX_FILE_SIZE_MB,
    collect,
    sync,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Condense ingestion agent")
    parser.add_argument("paths", nargs="+", help="one or more folders (or files) to ingest")
    parser.add_argument("--server", default=os.environ.get("SIFT_SERVER"), help="Sift base URL")
    parser.add_argument("--token", default=os.environ.get("SIFT_TOKEN"), help="bearer token")
    parser.add_argument("--tenant", default="default", help="target tenant")
    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="HTTP timeout in seconds for engine requests (default: 600)",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        default=list(DEFAULT_INCLUDE),
        help="file extensions to upload",
    )
    parser.add_argument("--dry-run", action="store_true", help="list uploads without sending")
    parser.add_argument(
        "--max-file-size-mb",
        type=int,
        default=DEFAULT_MAX_FILE_SIZE_MB,
        help="skip (with a warning) any file larger than this, in MB",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="run continuously, re-syncing on every change (replace-aware)",
    )
    parser.add_argument(
        "--delete-removed",
        action="store_true",
        help="with --watch: delete a document from the index when its file leaves disk",
    )
    parser.add_argument(
        "--exclude-dir",
        nargs="*",
        default=[],
        help=(
            "extra directory names to prune from the walk, merged with the built-in vendored/"
            f"tooling exclusions ({', '.join(sorted(DEFAULT_EXCLUDE_DIRS))})"
        ),
    )
    parser.add_argument(
        "--exclude-file",
        nargs="*",
        default=[],
        help=(
            "extra filename glob patterns to skip, merged with the built-in junk-filename "
            f"exclusions ({', '.join(sorted(DEFAULT_EXCLUDE_FILES))})"
        ),
    )
    return parser


def _watch(args: argparse.Namespace, client: SiftClient) -> int:
    """Continuous mode: full sync now, then re-sync (debounced) on every filesystem change."""
    from agent.watcher import Watcher  # local import so one-shot mode needs no watchdog

    includes = set(args.include)
    exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(args.exclude_dir)
    exclude_files = DEFAULT_EXCLUDE_FILES | set(args.exclude_file)
    managed: set[str] = set()  # paths seen on disk so far — scopes --delete-removed safely

    def run() -> None:
        nonlocal managed
        summary = sync(
            client,
            args.paths,
            includes,
            tenant=args.tenant,
            delete_removed=args.delete_removed,
            managed=managed,
            max_file_size_mb=args.max_file_size_mb,
            exclude_dirs=exclude_dirs,
            exclude_files=exclude_files,
        )
        managed = set(summary.managed)
        print(f"[sync] {summary.line()}")

    run()  # initial pass
    watcher = Watcher(args.paths, run, recursive=True)
    watcher.start()
    print(f"[watch] {', '.join(args.paths)} — Ctrl-C to stop")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        watcher.stop()
    return 0


def main(argv: list[str] | None = None, client: SiftClient | None = None) -> int:
    """Run the ingest flow; return a process exit code (0 on success)."""
    args = _build_parser().parse_args(argv)
    client = client or SiftClient(args.server, args.token, timeout=args.timeout)

    if args.watch:
        return _watch(args, client)

    includes = set(args.include)
    exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(args.exclude_dir)
    exclude_files = DEFAULT_EXCLUDE_FILES | set(args.exclude_file)
    files = [
        f
        for path in args.paths
        for f in collect(
            path,
            includes,
            max_file_size_mb=args.max_file_size_mb,
            exclude_dirs=exclude_dirs,
            exclude_files=exclude_files,
        )
    ]
    known = client.manifest(args.tenant)
    todo = [(rel, h, data, mtime) for rel, h, data, mtime in files if h not in known]
    if not todo:
        print("nothing to upload (all known)")
        return 0
    if args.dry_run:
        for rel, h, _data, _m in todo:
            print(f"WOULD UPLOAD {rel} ({h})")
        return 0
    try:
        resp = client.ingest(
            args.tenant,
            [(rel, data) for rel, _h, data, _m in todo],
            modified_at={rel: mtime for rel, _h, _data, mtime in todo},
        )
    except PartialIngestError as exc:
        # One or more batches landed before a later one failed (A4) — print every status the
        # server actually confirmed rather than nothing, then a clear, greppable summary so a
        # partial ingest can never read as either "silent success" or "total failure".
        results = exc.partial.get("results", [])
        for r in results:
            print(f"{r['status']}\t{r['path']}")
        indexed = sum(1 for r in results if r.get("status") == "indexed")
        skipped = sum(1 for r in results if r.get("status") == "skipped_dedup")
        failed = sum(1 for r in results if r.get("status") == "failed")
        never_attempted = len(todo) - len(results)
        print(
            f"PARTIAL: {indexed} indexed, {skipped} skipped, {failed} failed, "
            f"{never_attempted} of {len(todo)} files never attempted ({exc})"
        )
        return 1
    for r in resp["results"]:
        print(f"{r['status']}\t{r['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
