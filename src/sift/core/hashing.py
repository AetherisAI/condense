"""Content hashing shared across the parser, ingest dedup, and the agent (stdlib only).

A single sha256-of-raw-bytes implementation so every layer that hashes a file agrees: the
manifest the agent diffs against and the ``content_hash`` the parser stamps onto a Document
are computed identically here.
"""

from __future__ import annotations

import hashlib


def content_hash(data: bytes) -> str:
    """Return the hex sha256 digest of ``data`` — the canonical file content hash."""
    return hashlib.sha256(data).hexdigest()
