"""Token-windowing chunker: the :class:`~sift.core.ports.Chunker` adapter (plan §2).

Slides fixed-size token windows across a document's text and decodes each window back
to text, so every chunk is sized in the *tokenizer's* units (not characters). The
tokenizer is config-driven behind a tiny internal encode/decode abstraction so switching
between the offline ``tiktoken`` fallback and bge-m3's own tokenizer is a pure config
flip — no chunker logic changes.

The class default is ``tiktoken`` (light, fully offline, no torch) so direct construction
and unit tests stay network-free; the *system* default (wired by config) is ``bge-m3``,
whose tokenizer is loaded lazily only when selected.

**Degenerate-chunk floor (DECISIONS.md D50):** a fixed-size token window is sized purely in
tokens, so a window whose start happens to land on whitespace/template filler (e.g. a document's
padding, a repeated footer, a mostly-blank template section) can decode to a handful of real
characters (`"do. /"`, `"plantilla.)*"` were observed live) — a "genuine" window in the sense
that it really is what those tokens decode to, but useless as a retrievable/embeddable chunk,
and it still got indexed and surfaced. ``chunk_min_chars`` drops (never merges) any window whose
decoded, whitespace-collapsed text falls below the floor; the emitted ``index`` stays
document-global 0..n-1 over exactly the chunks that *are* emitted, so dropping a chunk never
leaves a gap for the store to reason about (its ``PRIMARY KEY (tenant, source_hash, idx)`` only
needs uniqueness + a stable order, never assumes indices map 1:1 to token-window positions).
"""

from __future__ import annotations

import asyncio
import re
from typing import Final, Protocol

from sift.core.types import Chunk, Document

# Collapses any run of whitespace to a single space, purely to measure a window's "real content"
# length for the `chunk_min_chars` floor (D50) — the emitted `Chunk.text` itself stays exactly
# the tokenizer's decode+strip, unchanged from before this floor existed.
_WHITESPACE_RE: Final = re.compile(r"\s+")


class _Tokenizer(Protocol):
    """The minimal encode/decode surface the windower needs (sync, pure-CPU)."""

    def encode(self, text: str) -> list[int]: ...

    def decode(self, ids: list[int]) -> str: ...


class _TiktokenTokenizer:
    """``cl100k_base`` via tiktoken — the offline fallback encoder."""

    def __init__(self) -> None:
        # Local import so selecting tiktoken never drags in tokenizers/huggingface_hub.
        import tiktoken

        self._enc = tiktoken.get_encoding("cl100k_base")

    def encode(self, text: str) -> list[int]:
        return self._enc.encode(text)

    def decode(self, ids: list[int]) -> str:
        return self._enc.decode(ids)


class _BgeM3Tokenizer:
    """bge-m3's own XLM-RoBERTa tokenizer — loaded lazily only when selected."""

    def __init__(self) -> None:
        # Local import so the tiktoken path never imports tokenizers/huggingface_hub;
        # ``from_pretrained`` performs a one-time fetch of bge-m3's ``tokenizer.json``.
        from tokenizers import Tokenizer

        self._tok = Tokenizer.from_pretrained("BAAI/bge-m3")

    def encode(self, text: str) -> list[int]:
        return self._tok.encode(text).ids

    def decode(self, ids: list[int]) -> str:
        return self._tok.decode(ids)


class TokenChunker:
    """Document → token-windowed chunks.

    Windows of ``chunk_size`` tokens slide across the whole document's token stream,
    stepping by ``step = chunk_size - chunk_overlap`` so adjacent windows share
    ``chunk_overlap`` tokens. Each window is decoded back to text and stripped; empty windows
    and windows whose whitespace-collapsed text is shorter than ``chunk_min_chars`` are both
    dropped (D50 — see the module docstring). ``index`` is a document-global 0-based ordinal
    over the emitted chunks (never the window's token-stream position), and ``page`` is the
    page that the window's *start* token falls in (always the sole page's number under
    markitdown's single-page parsing). Pure-CPU and deterministic — the ``async def`` never
    awaits, so identical input yields identical chunks/indices.
    """

    def __init__(
        self,
        *,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        tokenizer: str = "tiktoken",
        chunk_min_chars: int = 24,
    ) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap ({chunk_overlap}) must be < chunk_size ({chunk_size})")
        if chunk_min_chars < 1:
            raise ValueError(f"chunk_min_chars ({chunk_min_chars}) must be >= 1")
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._step = chunk_size - chunk_overlap
        self._chunk_min_chars = chunk_min_chars
        self._tokenizer = self._make_tokenizer(tokenizer)

    @staticmethod
    def _make_tokenizer(name: str) -> _Tokenizer:
        if name == "tiktoken":
            return _TiktokenTokenizer()
        if name == "bge-m3":
            return _BgeM3Tokenizer()
        raise ValueError(f"unknown tokenizer {name!r}; expected 'tiktoken' or 'bge-m3'")

    async def chunk(self, doc: Document) -> list[Chunk]:
        # Tokenization is pure-CPU and can be heavy (a full encode of the document plus a decode
        # per window over the bge-m3 Rust / tiktoken tokenizer). Offload it to a worker thread —
        # exactly as MarkitdownParser does its conversion — so a large-document ingest doesn't
        # stall the shared event loop and starve concurrent searches. Determinism is unchanged:
        # identical input still yields identical chunks/indices.
        return await asyncio.to_thread(self._chunk_sync, doc)

    def _chunk_sync(self, doc: Document) -> list[Chunk]:
        # Build the document-level token stream page by page so every token's source page
        # is known (the window's start token → its page). For markitdown's single page
        # this is exactly one encode of the whole document; multi-page is best-effort.
        token_ids: list[int] = []
        page_of_token: list[int] = []
        for page in doc.pages:
            ids = self._tokenizer.encode(page.text)
            token_ids.extend(ids)
            page_of_token.extend(page.number for _ in ids)

        chunks: list[Chunk] = []
        index = 0
        for start in range(0, len(token_ids), self._step):
            window = token_ids[start : start + self._chunk_size]
            text = self._tokenizer.decode(window).strip()
            if not text:
                continue
            # D50: a window can decode to real-but-useless text (whitespace/template filler the
            # window's start happened to land on) — measure the whitespace-COLLAPSED length so a
            # window that's mostly whitespace between a couple of stray characters is caught too,
            # while `text` itself (what gets embedded/stored) stays the plain decode+strip.
            if len(_WHITESPACE_RE.sub(" ", text).strip()) < self._chunk_min_chars:
                continue
            chunks.append(
                Chunk(
                    text=text,
                    source_path=doc.path,
                    page=page_of_token[start],
                    source_hash=doc.content_hash,
                    index=index,
                    vector=None,
                )
            )
            index += 1
        return chunks
