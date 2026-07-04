"""Tests for OcrFallbackParser — the parse → OCR fallback routing (no network).

Two small in-test fakes stand in for the primary :class:`~sift.core.ports.Parser` and the
:class:`~sift.adapters.ocr.mistral.MistralOcr` extractor, so we assert *routing* only: a doc
with real text passes straight through (OCR is never called), an empty or failed parse falls
back to OCR's text, and the genuinely-empty cases behave per contract. The fake OCR raises if
invoked when it should not be, turning an unwanted call into a test failure.
"""

from __future__ import annotations

import pytest

from sift.adapters.ocr.fallback_parser import OcrFallbackParser
from sift.core.errors import ParseError
from sift.core.types import Document, Page


class _PrimaryStub:
    """A primary Parser returning a fixed Document (or raising) — never touches the network."""

    def __init__(self, doc: Document | None = None, *, error: Exception | None = None) -> None:
        self._doc = doc
        self._error = error

    async def parse(self, data: bytes, filename: str) -> Document:
        if self._error is not None:
            raise self._error
        assert self._doc is not None
        return self._doc


class _OcrStub:
    """A MistralOcr stand-in returning canned text; records whether it was called."""

    def __init__(self, text: str = "", *, fail_if_called: bool = False) -> None:
        self._text = text
        self._fail_if_called = fail_if_called
        self.called = False

    async def extract(self, data: bytes, filename: str) -> str:
        if self._fail_if_called:
            raise AssertionError("OCR must not run when the primary parser found text")
        self.called = True
        return self._text


async def test_passthrough_when_primary_has_text() -> None:
    doc = Document(path="a.pdf", content_hash="h", pages=(Page(number=1, text="real text"),))
    ocr = _OcrStub(fail_if_called=True)
    parser = OcrFallbackParser(_PrimaryStub(doc), ocr)  # type: ignore[arg-type]

    result = await parser.parse(b"%PDF-...", "a.pdf")

    assert result is doc
    assert ocr.called is False


async def test_fallback_to_ocr_when_pages_empty() -> None:
    empty = Document(path="scan.png", content_hash="h", pages=(Page(number=1, text="   "),))
    ocr = _OcrStub("extracted text")
    parser = OcrFallbackParser(_PrimaryStub(empty), ocr)  # type: ignore[arg-type]

    result = await parser.parse(b"\x89PNG...", "scan.png")

    assert ocr.called is True
    assert [page.text for page in result.pages] == ["extracted text"]
    assert result.pages[0].number == 1
    assert result.path == "scan.png"


async def test_reraises_siftError_unchanged_without_touching_ocr() -> None:
    # A deliberate domain-level rejection (e.g. the xlsx used-range guard's ParseError, D34) is
    # not "the primary parser found no text" — it's a considered refusal to attempt an unsafe
    # parse at all. It must propagate unchanged (same instance, same message) and never trigger
    # OCR: no fallback text, no network call, no confusing OCR-side error replacing the real one.
    ocr = _OcrStub(fail_if_called=True)
    original = ParseError("sheet dimension implies 44,040,066 cells")
    primary = _PrimaryStub(error=original)
    parser = OcrFallbackParser(primary, ocr)  # type: ignore[arg-type]

    with pytest.raises(ParseError) as exc_info:
        await parser.parse(b"PK\x03\x04...", "huge.xlsx")

    assert exc_info.value is original
    assert ocr.called is False


async def test_fallback_to_ocr_when_primary_raises() -> None:
    ocr = _OcrStub("recovered text")
    primary = _PrimaryStub(error=RuntimeError("bad bytes"))
    parser = OcrFallbackParser(primary, ocr)  # type: ignore[arg-type]

    result = await parser.parse(b"???", "broken.pdf")

    assert ocr.called is True
    assert result.pages[0].text == "recovered text"


async def test_returns_primary_doc_when_ocr_finds_nothing() -> None:
    # Primary produced a (whitespace-only) Document and OCR also found nothing: hand the primary
    # doc back rather than raising, so the ingest pipeline still records the file's hash.
    empty = Document(path="blank.pdf", content_hash="h", pages=(Page(number=1, text="  "),))
    parser = OcrFallbackParser(_PrimaryStub(empty), _OcrStub(""))  # type: ignore[arg-type]

    result = await parser.parse(b"data", "blank.pdf")

    assert result is empty


async def test_raises_when_primary_fails_and_ocr_empty() -> None:
    # Primary *raised* (no doc at all) and OCR found nothing → nothing to index; surface a clear
    # error (the ingest pipeline isolates it as a per-file failure).
    primary = _PrimaryStub(error=RuntimeError("corrupt"))
    parser = OcrFallbackParser(primary, _OcrStub(""))  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        await parser.parse(b"data", "x.png")
