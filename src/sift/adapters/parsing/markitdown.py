"""Real :class:`~sift.core.ports.Parser` adapter backed by ``markitdown``.

Every supported file format is flattened to a single ``Page(number=1)`` — citations are
file-level for now, but ``Page.number`` stays in the contract so a real per-page parser
(e.g. pypdf) is a later adapter swap, not a rewrite. The blocking ``markitdown`` conversion
runs in a worker thread so the ``async def parse`` port method never stalls the event loop.

Pinned to ``markitdown`` 0.1.x: it exposes ``convert_stream(BytesIO, stream_info=StreamInfo(
extension=...))`` (older releases used ``convert(stream, file_extension=...)``).

**xlsx used-range guard (DECISIONS.md D34):** markitdown's xlsx converter is
``pandas.read_excel(stream, sheet_name=None, engine="openpyxl")`` — it materializes every row
and column implied by each sheet's *declared* dimension, not just its real content. A single
stray far cell (e.g. a paste/drag-fill artifact later blanked, which is exactly what a real
Acme corpus file had) inflates that declared range into the millions of rows; a real 38KB
``.xlsx`` reproduced under a ``MemoryMax=2G`` isolation scope climbed past 2GiB RSS and was
cgroup-OOM-killed rather than complete. ``_guard_xlsx_used_range`` does a cheap, read-only
inspection of each worksheet XML's ``<dimension ref="...">`` (no workbook load, no pandas) and
raises :class:`~sift.core.errors.ParseError` before the conversion if any sheet's implied cell
count exceeds ``max_xlsx_cells`` — an explicit, fast, human-readable failure instead of an
unbounded parse attempt.
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import zipfile
from typing import Final

from charset_normalizer import from_bytes
from markitdown import MarkItDown, StreamInfo
from openpyxl.utils.cell import range_boundaries

from sift.core.errors import ParseError
from sift.core.hashing import content_hash
from sift.core.types import Document, Page

# Matches the worksheet's declared used-range, e.g. `<dimension ref="B1:AQ1048573"/>`.
_XLSX_DIMENSION_RE: Final = re.compile(rb'<dimension[^>]*\bref="([^"]+)"')


class MarkitdownParser:
    """Bytes → a single-page :class:`~sift.core.types.Document` via ``markitdown``."""

    def __init__(self, *, max_xlsx_cells: int = 2_000_000) -> None:
        # Plugins are third-party and may touch the network/exec; keep parsing hermetic.
        self._md = MarkItDown(enable_plugins=False)
        # Config-driven via `Settings.parse_max_xlsx_cells` (factory.py wires it) — see the
        # module docstring / DECISIONS.md D34 for why this guard exists at all.
        self._max_xlsx_cells = max_xlsx_cells

    async def parse(self, data: bytes, filename: str) -> Document:
        """Parse ``data`` (the raw bytes of ``filename``) into a one-page Document."""
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".xlsx":
            self._guard_xlsx_used_range(data, filename)
        text = await asyncio.to_thread(self._convert, data, filename)
        return Document(
            path=filename,
            content_hash=content_hash(data),
            pages=(Page(number=1, text=text),),
        )

    def _guard_xlsx_used_range(self, data: bytes, filename: str) -> None:
        """Raise :class:`ParseError` if any sheet's declared dimension implies an implausible
        cell count — before markitdown's pandas/openpyxl conversion ever runs.

        Read-only zip + regex inspection: no workbook load, no pandas. A file that isn't a
        valid zip, or a sheet with no/unparseable ``<dimension>``, is left to markitdown itself
        (this guard only ever narrows failures to the specific shape it has evidence for).
        """
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                sheet_names = [
                    name
                    for name in archive.namelist()
                    if re.fullmatch(r"xl/worksheets/[^/]+\.xml", name)
                ]
                for name in sheet_names:
                    match = _XLSX_DIMENSION_RE.search(archive.read(name))
                    if match is None:
                        continue
                    ref = match.group(1).decode("ascii", errors="replace")
                    try:
                        min_col, min_row, max_col, max_row = range_boundaries(ref)
                    except ValueError:
                        continue
                    if min_col is None or min_row is None or max_col is None or max_row is None:
                        continue
                    cells = (max_row - min_row + 1) * (max_col - min_col + 1)
                    if cells > self._max_xlsx_cells:
                        raise ParseError(
                            f"{filename}: sheet dimension {ref!r} implies {cells:,} cells, "
                            f"over parse_max_xlsx_cells={self._max_xlsx_cells:,} — likely a "
                            "stray far cell inflated the declared used range (check with "
                            "Excel's Ctrl+End); trim the sheet's real extent and re-ingest "
                            "rather than risk an unbounded parse."
                        )
        except zipfile.BadZipFile:
            return

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
