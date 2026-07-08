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

**``--json``** (added for the Tauri desktop sidecar, see DECISIONS.md D54): every line normally
printed to stdout becomes one NDJSON object instead (``emit``), so a supervising process can
parse progress/failures without scraping human text. Never changes exit codes; never touches
stderr. Human output (no flag) is byte-for-byte unchanged. **SIGTERM** (added alongside it,
D54 — a supervisor's ``kill()`` sends SIGTERM, not the Ctrl-C SIGINT this used to require) stops
``--watch`` the same clean way Ctrl-C always has: the watcher is stopped and the process exits 0.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import threading
from typing import Any

from agent.client import PartialIngestError, SiftClient

# Re-exported from the shared sync engine so there's a single source of truth (and so existing
# imports ``from agent.cli import collect`` keep working).
from agent.sync import (
    DEFAULT_EXCLUDE_DIRS,
    DEFAULT_EXCLUDE_FILES,
    DEFAULT_INCLUDE,
    DEFAULT_MAX_FILE_SIZE_MB,
    SkipDetail,
    Summary,
    collect,
    sync,
)


def emit(event: dict[str, Any]) -> None:
    """Print one NDJSON object to stdout — the whole of ``--json``'s wire format."""
    print(json.dumps(event), flush=True)


def _sync_event(summary: Summary) -> dict[str, Any]:
    """A :class:`~agent.sync.Summary` as the ``sync`` NDJSON event (shared by one-shot + watch)."""
    event: dict[str, Any] = {
        "event": "sync",
        "indexed": summary.indexed,
        "replaced": summary.replaced,
        "deleted": summary.deleted,
        "skipped": summary.skipped,
        "failed": summary.failed,
        "failures": [{"path": f.path, "error": f.error} for f in summary.failures],
        # Local skip decisions (oversized/excluded dir/excluded file/unsupported extension) — the
        # agent's own filtering, distinct from ``failures`` (server-rejected uploads). See
        # agent.sync.SkipDetail.
        "skipped_details": [{"path": s.path, "reason": s.reason} for s in summary.skipped_details],
    }
    if summary.error:
        event["error"] = summary.error
    return event


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
        "--json",
        action="store_true",
        help="emit NDJSON events on stdout instead of human-readable lines",
    )
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
    """Continuous mode: full sync now, then re-sync (debounced) on every filesystem change.

    Stops cleanly — ``watcher.stop()`` then exit 0 — on either Ctrl-C (SIGINT, via the usual
    ``KeyboardInterrupt``) or SIGTERM (a supervising process's ``kill()``, e.g. Tauri's sidecar
    manager, which never sends SIGINT). Both roads lead through the same ``stop_event.wait()``:
    the SIGTERM handler just sets it instead of raising.
    """
    from agent.watcher import Watcher  # local import so one-shot mode needs no watchdog

    includes = set(args.include)
    exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(args.exclude_dir)
    exclude_files = DEFAULT_EXCLUDE_FILES | set(args.exclude_file)
    managed: set[str] = set()  # paths seen on disk so far — scopes --delete-removed safely
    # Persistent (abspath -> mtime_ns, size, sha256) cache so each debounced re-sync only
    # re-hashes files that actually changed, not the whole tree every pass.
    hash_cache: dict[str, tuple[int, int, str]] = {}
    stop_event = threading.Event()

    def _on_sigterm(signum: int, frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _on_sigterm)

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
            hash_cache=hash_cache,
        )
        managed = set(summary.managed)
        if args.json:
            emit(_sync_event(summary))
        else:
            print(f"[sync] {summary.line()}")

    try:
        run()  # initial pass
        watcher = Watcher(args.paths, run, recursive=True)
        watcher.start()
        if args.json:
            emit(
                {
                    "event": "watch_started",
                    "paths": args.paths,
                    "delete_removed": args.delete_removed,
                }
            )
        else:
            print(f"[watch] {', '.join(args.paths)} — Ctrl-C to stop")
        try:
            stop_event.wait()
        except KeyboardInterrupt:  # Ctrl-C — same clean stop as a SIGTERM
            pass
        finally:
            watcher.stop()
    except Exception as exc:
        if not args.json:
            raise  # unchanged human behaviour: let it crash with a traceback
        emit({"event": "fatal", "error": str(exc)})
        return 1

    if args.json:
        emit({"event": "stopped"})
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
    # Shared across every ``args.paths`` root (mirrors ``sync()``'s own single ``skip_sink`` per
    # pass) so one-shot mode's "sync" events name local skip decisions the same way ``--watch``'s
    # do (see agent.sync.SkipDetail) — additive, never touches the human-mode output below.
    skip_sink: list[SkipDetail] = []
    files = [
        f
        for path in args.paths
        for f in collect(
            path,
            includes,
            max_file_size_mb=args.max_file_size_mb,
            exclude_dirs=exclude_dirs,
            exclude_files=exclude_files,
            skip_sink=skip_sink,
        )
    ]
    skipped_details_json = [{"path": s.path, "reason": s.reason} for s in skip_sink]
    # Everything below hits the network (manifest, then ingest) — guarded the same way _watch()
    # guards its own network calls: in --json mode, an unexpected error (e.g. the server being
    # unreachable) becomes one clean {"event": "fatal", ...} line instead of a raw traceback on
    # stdout; without --json, behaviour is unchanged (let it crash as it always has).
    try:
        known = client.manifest(args.tenant)
        todo = [(rel, h, data, mtime) for rel, h, data, mtime in files if h not in known]
        skipped_known = len(files) - len(todo)  # already on server — never even sent (D45 parity)
        if not todo:
            if args.json:
                emit(
                    {
                        "event": "sync",
                        "indexed": 0,
                        "replaced": 0,
                        "deleted": 0,
                        "skipped": skipped_known,
                        "failed": 0,
                        "failures": [],
                        "skipped_details": skipped_details_json,
                    }
                )
            else:
                print("nothing to upload (all known)")
            return 0
        if args.dry_run:
            if args.json:
                emit(
                    {
                        "event": "dry_run",
                        "would_upload": [{"path": rel, "hash": h} for rel, h, _data, _m in todo],
                    }
                )
            else:
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
            # One or more batches landed before a later one failed (A4) — report every status the
            # server actually confirmed rather than nothing, then a clear, greppable summary so a
            # partial ingest can never read as either "silent success" or "total failure".
            results = exc.partial.get("results", [])
            indexed = sum(1 for r in results if r.get("status") == "indexed")
            skipped = sum(1 for r in results if r.get("status") == "skipped_dedup")
            failed_results = [r for r in results if r.get("status") == "failed"]
            never_attempted = len(todo) - len(results)
            if args.json:
                emit(
                    {
                        "event": "sync",
                        "indexed": indexed,
                        "replaced": 0,
                        "deleted": 0,
                        "skipped": skipped_known + skipped,
                        "failed": len(failed_results),
                        "failures": [
                            {"path": r.get("path"), "error": r.get("detail")}
                            for r in failed_results
                        ],
                        "error": str(exc),
                        "never_attempted": never_attempted,
                        "skipped_details": skipped_details_json,
                    }
                )
            else:
                for r in results:
                    print(f"{r['status']}\t{r['path']}")
                print(
                    f"PARTIAL: {indexed} indexed, {skipped} skipped, {len(failed_results)} failed, "
                    f"{never_attempted} of {len(todo)} files never attempted ({exc})"
                )
            return 1
        results = resp["results"]
        if args.json:
            failed_results = [r for r in results if r.get("status") == "failed"]
            emit(
                {
                    "event": "sync",
                    "indexed": sum(1 for r in results if r.get("status") == "indexed"),
                    "replaced": 0,
                    "deleted": 0,
                    "skipped": skipped_known
                    + sum(1 for r in results if r.get("status") == "skipped_dedup"),
                    "failed": len(failed_results),
                    "failures": [
                        {"path": r.get("path"), "error": r.get("detail")} for r in failed_results
                    ],
                    "skipped_details": skipped_details_json,
                }
            )
        else:
            for r in results:
                print(f"{r['status']}\t{r['path']}")
        return 0
    except Exception as exc:
        if not args.json:
            raise  # unchanged human behaviour: let it crash with a traceback
        emit({"event": "fatal", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
