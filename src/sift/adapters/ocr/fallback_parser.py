"""OCR fallback Parser — wraps a primary :class:`~sift.core.ports.Parser` with image/scan OCR.

A structural :class:`~sift.core.ports.Parser`: it delegates to a primary parser (markitdown)
and only reaches for OCR when that parser fails *unexpectedly* or yields no extractable text —
i.e. a screenshot, a photo, or a scanned, text-less PDF. Normal documents pass straight through
untouched and the OCR endpoint is never called; only empty/failed parses are re-extracted via
:class:`~sift.adapters.ocr.mistral.MistralOcr` and returned as a single-page Document.

**A deliberate :class:`~sift.core.errors.SiftError` (e.g. the xlsx used-range guard's
``ParseError``, DECISIONS.md D34) is a considered refusal to attempt an unsafe parse, not "no
text found" — it always re-raises unchanged, never triggers OCR** (see DECISIONS.md D36). Only
parser-internal/unexpected exceptions (corrupt/unsupported bytes) fall through to OCR.

Wired in ``factory.py`` around ``MarkitdownParser`` when OCR is configured, so the ingest
pipeline never changes — it still sees one ``Parser`` behind the port.
"""

from __future__ import annotations

from sift.adapters.ocr.mistral import MistralOcr
from sift.core.errors import SiftError
from sift.core.hashing import content_hash
from sift.core.ports import Parser
from sift.core.types import Document, Page


class OcrFallbackParser:
    """A Parser that falls back to OCR when its primary yields no usable text."""

    def __init__(self, primary: Parser, ocr: MistralOcr) -> None:
        self._primary = primary
        self._ocr = ocr

    async def parse(self, data: bytes, filename: str) -> Document:
        try:
            doc: Document | None = await self._primary.parse(data, filename)
        except SiftError:
            # A deliberate domain-level rejection (e.g. the xlsx used-range guard's ParseError)
            # is not "found no text" — it's a considered refusal to attempt an unsafe parse at
            # all. Re-raise unchanged: no OCR attempt, no network call (D36).
            raise
        except Exception:
            # The primary parser choked on the bytes (corrupt/unsupported) — fall through to OCR
            # exactly as we do for a parse that simply found no text.
            doc = None
        # Pass-through: the primary already produced real text → return it, OCR untouched.
        if doc is not None and any(page.text.strip() for page in doc.pages):
            return doc
        text = await self._ocr.extract(data, filename)
        if text.strip():
            return Document(
                path=filename,
                content_hash=content_hash(data),
                pages=(Page(number=1, text=text),),
            )
        # OCR found nothing either: keep the primary doc if there was one (so the ingest
        # pipeline still records the file), otherwise there is genuinely nothing to index.
        if doc is not None:
            return doc
        raise ValueError(
            f"no extractable text in {filename!r}: "
            "the primary parser failed and OCR returned nothing"
        )
