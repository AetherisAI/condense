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
Leitat corpus file had) inflates that declared range into the millions of rows; a real 38KB
``.xlsx`` reproduced under a ``MemoryMax=2G`` isolation scope climbed past 2GiB RSS and was
cgroup-OOM-killed rather than complete. ``_guard_xlsx_used_range`` does a cheap, read-only
inspection of each worksheet XML's ``<dimension ref="...">`` (no workbook load, no pandas) and
raises :class:`~sift.core.errors.ParseError` before the conversion if any sheet's implied cell
count exceeds ``max_xlsx_cells`` — an explicit, fast, human-readable failure instead of an
unbounded parse attempt.

**Generic guardrails (DECISIONS.md D39):** the xlsx guard above is a pre-parse fix for one
specific failure shape; two further guards apply to *every* format as defense-in-depth against
production messiness generally: a post-parse extracted-text ceiling (``max_chars`` — a
``Document`` whose total text exceeds it raises :class:`ParseError` rather than ever being
silently truncated) and a per-file wall-clock timeout (``timeout_s`` — the blocking conversion
runs under ``asyncio.wait_for``, so a hung/pathologically slow parse fails that one file
explicitly instead of stalling the whole ingest batch).

**xlsx "NaN" cell-filler cleanup (DECISIONS.md D50):** markitdown's xlsx converter is
``pandas.read_excel(...).to_html()`` — pandas' ``to_html`` renders every empty/missing cell as
the literal string ``"NaN"`` (its ``na_rep`` default), not a genuine value. A real Leitat
budget spreadsheet with wide merged-cell headers and many partially-filled rows came back with
nearly 3,000 literal ``"NaN"`` occurrences — diluting embeddings and making snippets unreadable.
``_strip_xlsx_nan_fillers`` is a narrow, xlsx-only post-parse cleanup: it blanks a markdown-table
CELL only when its entire trimmed content is exactly ``"NaN"`` (never a substring match, never a
non-table line), so a genuine value like ``"NaNoTech Corp"`` and any other format's own literal
"NaN" text both survive untouched. Considered and rejected: a Condense-owned xlsx→text step that
bypasses markitdown's ``XlsxConverter`` entirely (``pandas``/``openpyxl`` read + ``df.fillna("")``
+ own multi-sheet/table rendering) — strictly more code re-implementing logic markitdown already
gets right (multi-sheet iteration, HTML→markdown table conversion), for a fix that is otherwise a
one-parameter change (``to_html``'s ``na_rep``, not exposed by markitdown's converter). The
post-parse cleanup is the lower-risk of the two: it never touches markitdown's own conversion
path, so multi-sheet output and any future markitdown xlsx improvements keep working unchanged.
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


def _strip_xlsx_nan_fillers(text: str) -> str:
    """Blank markdown-table cells whose entire (trimmed) content is exactly ``"NaN"`` (D50).

    Scoped to markdown TABLE rows only (a line that, once stripped, both starts and ends with
    ``|`` — exactly the shape markitdown's xlsx converter emits, one table per sheet) and to a
    whole-cell match — never a substring — so a genuine value like ``"NaNoTech Corp"`` or a
    non-table line survives untouched. Callers apply this only for ``.xlsx`` input; it is not a
    general-purpose "NaN" scrubber.
    """

    def _clean_row(line: str) -> str:
        cells = line.split("|")
        return "|".join(" " if cell.strip() == "NaN" else cell for cell in cells)

    lines = text.split("\n")
    return "\n".join(
        _clean_row(line) if line.strip().startswith("|") and line.strip().endswith("|") else line
        for line in lines
    )


class MarkitdownParser:
    """Bytes → a single-page :class:`~sift.core.types.Document` via ``markitdown``."""

    def __init__(
        self,
        *,
        max_xlsx_cells: int = 2_000_000,
        max_chars: int = 2_000_000,
        timeout_s: float = 60.0,
    ) -> None:
        # Plugins are third-party and may touch the network/exec; keep parsing hermetic.
        self._md = MarkItDown(enable_plugins=False)
        # Config-driven via `Settings.parse_max_xlsx_cells`/`parse_max_chars`/`parse_timeout_s`
        # (factory.py wires them) — see the module docstring / DECISIONS.md D34/D39 for why these
        # guards exist. Defaults here mirror the `Settings` defaults so behaviour is correct even
        # before a caller threads the configured value through explicitly.
        self._max_xlsx_cells = max_xlsx_cells
        self._max_chars = max_chars
        self._timeout_s = timeout_s

    async def parse(self, data: bytes, filename: str) -> Document:
        """Parse ``data`` (the raw bytes of ``filename``) into a one-page Document.

        Two generic guards apply after the xlsx-specific pre-parse check above (D39): the
        conversion itself runs under a ``parse_timeout_s`` wall-clock budget, and the resulting
        text is rejected outright — never silently truncated — if it exceeds ``parse_max_chars``.
        For ``.xlsx`` specifically, empty-cell "NaN" filler text is blanked before that ceiling
        check (D50) — see :func:`_strip_xlsx_nan_fillers`.
        """
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".xlsx":
            self._guard_xlsx_used_range(data, filename)
        text = await self._convert_with_timeout(data, filename)
        if ext == ".xlsx":
            text = _strip_xlsx_nan_fillers(text)
        self._guard_text_ceiling(text, filename)
        return Document(
            path=filename,
            content_hash=content_hash(data),
            pages=(Page(number=1, text=text),),
        )

    async def _convert_with_timeout(self, data: bytes, filename: str) -> str:
        """Run the blocking ``markitdown`` conversion under a wall-clock budget.

        A hung or pathologically slow parse (a shape the xlsx used-range guard doesn't cover —
        e.g. a pathological pdf/docx) must fail *this one file* explicitly rather than stall the
        whole ingest batch behind it (DECISIONS.md D39). ``asyncio.wait_for`` cancels waiting on
        the timeout; the worker thread it started may keep running to completion in the
        background (Python threads can't be forcibly killed), but the caller never blocks on it.
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._convert, data, filename), timeout=self._timeout_s
            )
        except TimeoutError as exc:
            raise ParseError(
                f"{filename}: parse exceeded parse_timeout_s={self._timeout_s:g} seconds — "
                "failing this file explicitly rather than stalling the rest of the ingest batch."
            ) from exc

    def _guard_text_ceiling(self, text: str, filename: str) -> None:
        """Raise :class:`ParseError` if ``text`` (the full extracted content) is implausibly
        large — a generic, format-agnostic defense-in-depth ceiling (D39) alongside the
        xlsx-specific pre-parse guard above. Never truncates; always an explicit failure.
        """
        if len(text) > self._max_chars:
            raise ParseError(
                f"{filename}: extracted text is {len(text):,} chars, over parse_max_chars="
                f"{self._max_chars:,} — refusing rather than silently truncating; raise "
                "Settings.parse_max_chars if a file this large is genuinely expected."
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
