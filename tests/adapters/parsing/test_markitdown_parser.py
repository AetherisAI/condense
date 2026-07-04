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
