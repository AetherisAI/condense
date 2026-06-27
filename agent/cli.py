"""The ``agent`` command line: walk a folder, diff against the manifest, upload the rest.

stdlib ``argparse`` + ``os.walk`` + ``hashlib.sha256`` (deliberately the same hash the
server stamps, computed here without importing ``sift``). ``main`` takes an optional
``client`` so tests can inject a :class:`~agent.client.SiftClient` built on a
``httpx.MockTransport`` and run the whole flow offline.
"""

from __future__ import annotations

import argparse
import hashlib
import os

from agent.client import SiftClient

DEFAULT_INCLUDE = [".txt", ".md", ".pdf", ".docx", ".xlsx", ".pptx", ".html"]


def collect(root: str, includes: set[str]) -> list[tuple[str, str, bytes]]:
    """Walk ``root``; return ``(relpath, sha256_hex, data)`` for files matching ``includes``."""
    found: list[tuple[str, str, bytes]] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in includes:
                continue
            full = os.path.join(dirpath, name)
            with open(full, "rb") as fh:
                data = fh.read()
            rel = os.path.relpath(full, root)
            found.append((rel, hashlib.sha256(data).hexdigest(), data))
    return found


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="Sift ingestion agent")
    parser.add_argument("path", help="folder to ingest")
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
    return parser


def main(argv: list[str] | None = None, client: SiftClient | None = None) -> int:
    """Run the ingest flow; return a process exit code (0 on success)."""
    args = _build_parser().parse_args(argv)
    client = client or SiftClient(args.server, args.token)
    files = collect(args.path, set(args.include))
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
