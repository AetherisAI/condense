"""The ``agent`` command line: walk a folder, diff against the manifest, upload the rest.

Two modes:

* **one-shot** (default) — collect, diff against ``/ingest/manifest``, upload new files, exit.
  Deliberately the same content hash the server stamps, computed here without importing ``sift``.
* **--watch** — run the continuous, replace-aware :func:`agent.sync.sync` engine on every change
  (the headless twin of the desktop app), optionally deleting docs whose files leave disk.

``main`` takes an optional ``client`` so tests can inject a :class:`~agent.client.SiftClient`
built on an ``httpx.MockTransport`` and run the whole flow offline.
"""

from __future__ import annotations

import argparse
import os
import threading

from agent.client import SiftClient

# Re-exported from the shared sync engine so there's a single source of truth (and so existing
# imports ``from agent.cli import collect`` keep working).
from agent.sync import DEFAULT_INCLUDE, collect, sync


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Condense ingestion agent")
    parser.add_argument("paths", nargs="+", help="one or more folders (or files) to ingest")
    parser.add_argument("--server", default=os.environ.get("SIFT_SERVER"), help="Sift base URL")
    parser.add_argument("--token", default=os.environ.get("SIFT_TOKEN"), help="bearer token")
    parser.add_argument("--tenant", default="default", help="target tenant")
    parser.add_argument(
        "--include",
        nargs="*",
        default=list(DEFAULT_INCLUDE),
        help="file extensions to upload",
    )
    parser.add_argument("--dry-run", action="store_true", help="list uploads without sending")
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
    return parser


def _watch(args: argparse.Namespace, client: SiftClient) -> int:
    """Continuous mode: full sync now, then re-sync (debounced) on every filesystem change."""
    from agent.watcher import Watcher  # local import so one-shot mode needs no watchdog

    includes = set(args.include)
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
    client = client or SiftClient(args.server, args.token)

    if args.watch:
        return _watch(args, client)

    includes = set(args.include)
    files = [f for path in args.paths for f in collect(path, includes)]
    known = client.manifest(args.tenant)
    todo = [(rel, h, data) for rel, h, data in files if h not in known]
    if not todo:
        print("nothing to upload (all known)")
        return 0
    if args.dry_run:
        for rel, h, _data in todo:
            print(f"WOULD UPLOAD {rel} ({h})")
        return 0
    resp = client.ingest(args.tenant, [(rel, data) for rel, _h, data in todo])
    for r in resp["results"]:
        print(f"{r['status']}\t{r['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
