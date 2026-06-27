"""The Sift ingestion agent — a standalone CLI that never imports ``sift``.

It walks a folder, hashes each file with stdlib ``hashlib.sha256``, diffs against the
server's manifest, and uploads only new/changed files over the frozen wire contract
(``GET /ingest/manifest`` + ``POST /ingest``). Its only runtime dependency is ``httpx``.
"""

from __future__ import annotations
