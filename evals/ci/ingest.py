"""Ingest every ``*.md`` under a folder into the store the environment points at.

    TURSO_DATABASE_URL=file:eval-ci.db python evals/ci/ingest.py evals/ci/corpus [--env-file F]

Uses the same ``Settings`` + ``build_container`` as the server, so the CI gate measures the real
parse → chunk → embed → store path. Paths are stored relative to the folder, which is what the
golden set's ``relevant`` paths match. Exits 1 if any file fails to ingest. Like ``sift-eval``,
it reads ``./.env`` unless ``--env-file`` points elsewhere (``/dev/null`` for none).
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import time
from pathlib import Path

from sift.eval.config import load_settings
from sift.factory import build_container

BATCH = 50


async def ingest(corpus: Path, env_file: Path | None) -> int:
    app, es = load_settings(env_file)
    container = build_container(app, ephemeral_conversations=True)
    files = sorted(corpus.rglob("*.md"))
    print(f"store {app.turso_database_url}, {len(files)} files", flush=True)
    totals: collections.Counter[str] = collections.Counter()
    chunks = 0
    start = time.monotonic()
    for i in range(0, len(files), BATCH):
        batch = files[i : i + BATCH]
        payload = [(p.relative_to(corpus).as_posix(), p.read_bytes()) for p in batch]
        for outcome in await container.ingest.ingest(payload, es.tenant):
            totals[outcome.status] += 1
            chunks += outcome.chunks or 0
            if outcome.status == "failed":
                print(f"FAILED {outcome.path}: {outcome.detail}", flush=True)
        elapsed = time.monotonic() - start
        print(f"{i + len(batch)}/{len(files)} chunks={chunks} {elapsed:.0f}s", flush=True)
    print(f"done: {dict(totals)} chunks={chunks} in {time.monotonic() - start:.0f}s", flush=True)
    return 1 if totals["failed"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a folder of Markdown into the store")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--env-file", type=Path, help="config file (default: ./.env)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(ingest(args.corpus, args.env_file)))
