"""Mistral OCR adapter — bytes → extracted markdown text over async HTTP.

The text extractor behind the OCR fallback: it base64-encodes the raw file and POSTs it to
Mistral's ``{base_url}/ocr`` endpoint, sending an inline ``image_url`` data URI for image
extensions and a ``document_url`` (PDF) data URI for everything else (PDFs, and anything else
the primary parser failed on). The response's per-page ``markdown`` is joined into one string.

Mirrors the inference adapters' style — one ``httpx.AsyncClient`` per call (no shared state),
bearer auth, ``raise_for_status`` — and stays out of ``core``/``pipelines``: only the
:class:`~sift.adapters.ocr.fallback_parser.OcrFallbackParser` (and ``factory``) know it exists.
"""

from __future__ import annotations

import base64
import os

import httpx

# Image extensions go up as an inline ``image_url`` data URI carrying their own MIME type; every
# other extension is sent as a PDF ``document_url`` — Mistral OCR reads both shapes.
_IMAGE_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
}
_TIMEOUT = httpx.Timeout(120.0)


class MistralOcr:
    """OCR extractor backed by Mistral's ``/ocr`` HTTP endpoint."""

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    async def extract(self, data: bytes, filename: str) -> str:
        """OCR ``data`` (the raw bytes of ``filename``) into joined markdown, or ``""``."""
        b64 = base64.b64encode(data).decode("ascii")
        ext = os.path.splitext(filename)[1].lower()
        mime = _IMAGE_MIMES.get(ext)
        document: dict[str, str]
        if mime is not None:
            document = {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"}
        else:
            document = {
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{b64}",
            }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        payload = {"model": self._model, "document": document}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(f"{self._base_url}/ocr", json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        pages = body.get("pages") or []
        texts = [page["markdown"] for page in pages if (page.get("markdown") or "").strip()]
        return "\n\n".join(texts)
