"""Unit tests for TokenChunker (offline tiktoken path; pytest-asyncio auto mode)."""

from __future__ import annotations

import pytest

from sift.adapters.chunking.token import TokenChunker
from sift.core.ports import Chunker
from sift.core.types import Document, Page

tiktoken = pytest.importorskip("tiktoken")


def _doc(text: str, *, page_number: int = 1, path: str = "doc.md", h: str = "hash0") -> Document:
    return Document(path=path, content_hash=h, pages=(Page(number=page_number, text=text),))


def test_satisfies_chunker_port() -> None:
    impl: Chunker = TokenChunker(tokenizer="tiktoken")
    assert isinstance(impl, Chunker)


def test_overlap_ge_size_raises() -> None:
    with pytest.raises(ValueError):
        TokenChunker(chunk_size=10, chunk_overlap=10, tokenizer="tiktoken")
    with pytest.raises(ValueError):
        TokenChunker(chunk_size=10, chunk_overlap=11, tokenizer="tiktoken")


async def test_short_page_yields_single_chunk() -> None:
    doc = _doc("Hello world, this is a short page.", page_number=7)
    chunker = TokenChunker(chunk_size=512, chunk_overlap=64, tokenizer="tiktoken")

    chunks = await chunker.chunk(doc)

    assert len(chunks) == 1
    only = chunks[0]
    assert only.index == 0
    assert only.page == doc.pages[0].number == 7
    assert only.vector is None
    assert only.source_path == doc.path
    assert only.source_hash == doc.content_hash
    assert only.text == "Hello world, this is a short page."


async def test_empty_text_yields_no_chunks() -> None:
    chunker = TokenChunker(chunk_size=10, chunk_overlap=4, tokenizer="tiktoken")
    assert await chunker.chunk(_doc("")) == []


async def test_long_text_windowing_matches_reference() -> None:
    size, overlap = 10, 4
    step = size - overlap
    text = "token test sentence number alpha beta gamma delta " * 12
    doc = _doc(text, page_number=3)
    chunker = TokenChunker(chunk_size=size, chunk_overlap=overlap, tokenizer="tiktoken")

    chunks = await chunker.chunk(doc)

    # Reference: encode the same text once and slide identical windows.
    enc = tiktoken.get_encoding("cl100k_base")
    ids = enc.encode(text)
    assert len(ids) > size  # the fixture must actually span multiple windows
    windows = [ids[i : i + size] for i in range(0, len(ids), step)]
    expected = [t for w in windows if (t := enc.decode(w).strip())]

    # Expected number of (non-empty) windows.
    assert len(chunks) == len(expected) > 1
    # Each chunk's text is the decoded+stripped window, in order.
    assert [c.text for c in chunks] == expected
    # index is global-sequential 0..n-1.
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # page is the single page's number for every chunk.
    assert {c.page for c in chunks} == {3}

    # Every token window is <= chunk_size tokens.
    assert all(len(w) <= size for w in windows)
    # Adjacent windows share exactly chunk_overlap tokens (where both are full windows).
    for a, b in zip(windows, windows[1:], strict=False):
        if len(a) == size and len(b) >= overlap:
            assert a[-overlap:] == b[:overlap]


async def test_deterministic_same_doc_twice() -> None:
    doc = _doc("token test sentence number alpha beta gamma " * 8, page_number=2)
    chunker = TokenChunker(chunk_size=12, chunk_overlap=3, tokenizer="tiktoken")

    first = await chunker.chunk(doc)
    second = await chunker.chunk(doc)

    assert first == second
    assert len(first) > 1
