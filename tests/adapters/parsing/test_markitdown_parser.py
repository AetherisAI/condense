"""Tests for :class:`~sift.adapters.parsing.markitdown.MarkitdownParser`.

Offline-only: a tiny UTF-8 ``.txt`` exercises the full parse path with no binary fixtures
and no network. Guarded with ``importorskip`` so base CI (no ``[parsing]`` extra) skips
cleanly instead of erroring on the ``markitdown`` import.
"""

from __future__ import annotations

import hashlib
import io

import pytest

pytest.importorskip("markitdown")
openpyxl = pytest.importorskip("openpyxl")

from sift.adapters.parsing.markitdown import MarkitdownParser  # noqa: E402
from sift.core.errors import ParseError  # noqa: E402
from sift.core.hashing import content_hash  # noqa: E402
from sift.core.ports import Parser  # noqa: E402
from sift.core.types import Document  # noqa: E402

SAMPLE_TEXT = "Hello, Sift! This is a tiny markitdown parsing test.\n"
SAMPLE_BYTES = SAMPLE_TEXT.encode("utf-8")


def _xlsx_with_stray_far_cell() -> bytes:
    """A tiny ``.xlsx`` whose real content is one cell, but whose *declared* used-range
    balloons to over a million rows — the exact shape found in DECISIONS.md D34's incident
    (a stray far cell, e.g. from a dropdown/paste artifact, that was later blanked but left
    openpyxl's own dimension bookkeeping — and hence the real-world file's — inflated).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "hello"
    ws["C1048573"] = "stray"
    ws["C1048573"] = None
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _small_xlsx() -> bytes:
    """A normal small ``.xlsx`` — no stray far cells, well under any sane cell-count guard."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "value"])
    ws.append(["alpha", 1])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _xlsx_with_empty_cells() -> bytes:
    """Empty cells sitting next to real values in the same row — the exact shape that produces
    literal ``"NaN"`` filler text via pandas' ``DataFrame.to_html()`` default ``na_rep="NaN"``
    (DECISIONS.md D50): markitdown's ``XlsxConverter`` is ``pandas.read_excel(...).to_html()``,
    and an empty cell reads back as a missing value, rendered as the literal string ``"NaN"``.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "value", "note"])
    ws.append(["alpha", 1, None])
    ws.append([None, 2, "beta-note"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _xlsx_with_nan_substring_cell() -> bytes:
    """A cell whose real content merely *contains* "NaN" as a substring — must survive the
    empty-cell-filler cleanup untouched (only a cell whose ENTIRE trimmed content is exactly
    "NaN" is ever blanked)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["vendor", "amount"])
    ws.append(["NaNoTech Corp", 500])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_satisfies_parser_port() -> None:
    impl: Parser = MarkitdownParser()
    assert isinstance(impl, Parser)


async def test_parses_txt_to_single_page_document() -> None:
    doc = await MarkitdownParser().parse(SAMPLE_BYTES, "note.txt")

    assert isinstance(doc, Document)
    assert doc.path == "note.txt"
    assert len(doc.pages) == 1

    (page,) = doc.pages
    assert page.number == 1
    assert "Hello, Sift!" in page.text


async def test_content_hash_is_sha256_of_raw_bytes() -> None:
    doc = await MarkitdownParser().parse(SAMPLE_BYTES, "note.txt")

    expected = hashlib.sha256(SAMPLE_BYTES).hexdigest()
    assert doc.content_hash == expected
    assert doc.content_hash == content_hash(SAMPLE_BYTES)


async def test_parse_is_stable_across_runs() -> None:
    parser = MarkitdownParser()
    first = await parser.parse(SAMPLE_BYTES, "note.txt")
    second = await parser.parse(SAMPLE_BYTES, "note.txt")

    assert first == second
    assert first.content_hash == second.content_hash
    assert first.pages[0].text == second.pages[0].text


async def test_parses_non_ascii_utf8_text() -> None:
    """A real-world .txt with em-dashes/curly quotes/accents must not fall back to ASCII.

    markitdown's PlainTextConverter guesses ASCII for a mostly-ASCII body and then raises
    ``UnicodeDecodeError: 'ascii' codec can't decode byte 0xe2`` on the first UTF-8 byte —
    exactly how a Project Gutenberg ``.txt`` (em-dash at byte 6477) failed to ingest. The
    single non-ASCII char sits deep in the body, past the charset-detection sample window,
    so the detector reports ASCII; the parser must still decode it as UTF-8.
    """
    data = (b"word " * 1600) + "end — dash\n".encode()
    assert data.index(b"\xe2") > 4096  # em-dash lands well past the detection sample

    doc = await MarkitdownParser().parse(data, "essay.txt")

    (page,) = doc.pages
    assert page.text.rstrip().endswith("end — dash")


async def test_xlsx_with_implausible_used_range_raises_parse_error() -> None:
    """DECISIONS.md D34: a real 38KB Acme ``.xlsx`` declared a ``B1:AQ1048573`` used-range
    (two stray cells at row ~1,048,572) and markitdown's ``pandas.read_excel(engine="openpyxl")``
    materialized that whole range, climbing past 2GiB RSS before it was cgroup-OOM-killed. The
    guard must reject this fast, with a clear reason, instead of ever attempting that parse.
    """
    parser = MarkitdownParser()

    with pytest.raises(ParseError, match=r"cells"):
        await parser.parse(_xlsx_with_stray_far_cell(), "schedule.xlsx")


async def test_xlsx_within_threshold_still_parses() -> None:
    """A normal small xlsx (no stray far cells) must be unaffected by the guard."""
    doc = await MarkitdownParser().parse(_small_xlsx(), "small.xlsx")

    assert "alpha" in doc.pages[0].text


async def test_xlsx_cell_threshold_is_configurable() -> None:
    """A caller-supplied threshold is honored — e.g. a stricter cap for a memory-tight host."""
    parser = MarkitdownParser(max_xlsx_cells=1)

    with pytest.raises(ParseError, match=r"parse_max_xlsx_cells=1\b"):
        await parser.parse(_small_xlsx(), "small.xlsx")


# ------------------------------------------------------------- xlsx NaN cell filler (D50)


async def test_xlsx_empty_cells_do_not_render_as_literal_nan() -> None:
    """DECISIONS.md D50: markitdown's xlsx converter renders every empty/missing cell as the
    literal string "NaN" (pandas' `to_html(na_rep="NaN")` default) — a dedup-diluting, unreadable
    artifact, not real content. Real values in the same row/sheet must survive untouched.
    """
    doc = await MarkitdownParser().parse(_xlsx_with_empty_cells(), "gaps.xlsx")
    text = doc.pages[0].text

    assert "NaN" not in text
    assert "alpha" in text
    assert "beta-note" in text


async def test_xlsx_cell_containing_nan_substring_is_preserved() -> None:
    """The cleanup only ever blanks a cell whose ENTIRE trimmed content is exactly "NaN" — a
    real value that merely contains "NaN" as a substring (e.g. a company name) must survive.
    """
    doc = await MarkitdownParser().parse(_xlsx_with_nan_substring_cell(), "vendor.xlsx")

    assert "NaNoTech Corp" in doc.pages[0].text


async def test_non_xlsx_literal_nan_text_is_untouched() -> None:
    """The NaN-filler cleanup is xlsx-specific — a `.txt` whose real prose happens to contain the
    word "NaN" (e.g. describing a sensor fault) must never be touched by it.
    """
    data = b"The temperature sensor returned NaN due to a fault."

    doc = await MarkitdownParser().parse(data, "sensor-log.txt")

    assert "NaN" in doc.pages[0].text


# ------------------------------------------------------------- parse_max_chars (generic ceiling)


async def test_text_over_max_chars_raises_parse_error() -> None:
    """A generic post-parse ceiling applies to *every* format (defense-in-depth alongside the
    xlsx-specific pre-parse guard above, D34/D39) — an oversized extracted `Document` must raise
    an explicit `ParseError`, never be silently truncated.
    """
    parser = MarkitdownParser(max_chars=10)

    with pytest.raises(ParseError, match=r"parse_max_chars=10\b"):
        await parser.parse(SAMPLE_BYTES, "note.txt")


async def test_text_under_max_chars_is_unaffected() -> None:
    """A file well under the ceiling parses normally — the guard never fires on ordinary input."""
    parser = MarkitdownParser(max_chars=10_000)

    doc = await parser.parse(SAMPLE_BYTES, "note.txt")

    assert "Hello, Sift!" in doc.pages[0].text


async def test_max_chars_default_matches_settings_default() -> None:
    """The constructor default (unwired) matches `Settings.parse_max_chars`'s default (2,000,000)
    so behaviour is correct out of the box even before `factory.py` threads the configured value
    through — see DECISIONS.md D39.
    """
    parser = MarkitdownParser()

    assert parser._max_chars == 2_000_000  # noqa: SLF001 — asserting the documented default


# ------------------------------------------------------------------ parse_timeout_s (wall clock)


async def test_slow_parse_raises_explicit_parse_error_after_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hung/pathologically slow parse must fail that one file explicitly instead of stalling
    the whole ingest batch — `asyncio.wait_for` around the blocking conversion, per DECISIONS.md
    D39. A deliberately slow fake `_convert` stands in for a hanging real converter.
    """
    import time

    def _slow_convert(self: MarkitdownParser, data: bytes, filename: str) -> str:
        time.sleep(0.3)
        return "irrelevant — should never be reached before the timeout fires"

    monkeypatch.setattr(MarkitdownParser, "_convert", _slow_convert)
    parser = MarkitdownParser(timeout_s=0.05)

    with pytest.raises(ParseError, match=r"parse_timeout_s=0.05\b"):
        await parser.parse(SAMPLE_BYTES, "slow.txt")


async def test_fast_parse_unaffected_by_timeout_guard() -> None:
    """A normal, fast parse must be unaffected by the timeout guard being present at all."""
    parser = MarkitdownParser(timeout_s=5.0)

    doc = await parser.parse(SAMPLE_BYTES, "note.txt")

    assert "Hello, Sift!" in doc.pages[0].text
