"""Real :class:`~sift.core.ports.Parser` adapter backed by ``markitdown``.

Every supported file format is flattened to a single ``Page(number=1)`` — citations are
file-level for now, but ``Page.number`` stays in the contract so a real per-page parser
(e.g. pypdf) is a later adapter swap, not a rewrite. The blocking ``markitdown`` conversion
runs in a worker thread so the ``async def parse`` port method never stalls the event loop.

Pinned to ``markitdown`` 0.1.x: it exposes ``convert_stream(BytesIO, stream_info=StreamInfo(
extension=...))`` (older releases used ``convert(stream, file_extension=...)``).
"""

from __future__ import annotations

import asyncio
import io
import os

from charset_normalizer import from_bytes
from markitdown import MarkItDown, StreamInfo

from sift.core.hashing import content_hash
from sift.core.types import Document, Page


class MarkitdownParser:
    """Bytes → a single-page :class:`~sift.core.types.Document` via ``markitdown``."""

    def __init__(self) -> None:
        # Plugins are third-party and may touch the network/exec; keep parsing hermetic.
        self._md = MarkItDown(enable_plugins=False)

    async def parse(self, data: bytes, filename: str) -> Document:
        """Parse ``data`` (the raw bytes of ``filename``) into a one-page Document."""
        text = await asyncio.to_thread(self._convert, data, filename)
        return Document(
            path=filename,
            content_hash=content_hash(data),
            pages=(Page(number=1, text=text),),
        )

    def _convert(self, data: bytes, filename: str) -> str:
        """Blocking markitdown conversion — runs off the event loop via ``to_thread``."""
        ext = os.path.splitext(filename)[1].lower()
        result = self._md.convert_stream(
            io.BytesIO(data),
            stream_info=StreamInfo(extension=ext or None, charset=self._charset(data)),
        )
        return result.text_content

    @staticmethod
    def _charset(data: bytes) -> str | None:
        """Best-guess text encoding so markitdown never falls back to ASCII.

        markitdown's PlainTextConverter decodes as ASCII whenever it cannot pin the charset,
        which raises ``UnicodeDecodeError`` on any non-ASCII UTF-8 (em-dashes, curly quotes,
        accents) — silently dropping most real-world text and Markdown. We detect with
        ``charset_normalizer`` (markitdown's own dependency) and pass the result in. A body
        that is ASCII except for one byte far past the sample window gets guessed as ``ascii``;
        since ASCII is a strict subset of UTF-8, we promote ``ascii``/unknown to ``utf-8`` so
        those bytes still decode. Binary formats (PDF, docx) ignore this hint.
        """
        if not data:
            return None
        match = from_bytes(data).best()
        encoding = match.encoding if match else None
        if not encoding or encoding == "ascii":
            return "utf-8"
        return encoding
