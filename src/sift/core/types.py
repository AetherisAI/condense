"""Pure domain types — the shared vocabulary every layer codes against.

stdlib only (the dependency rule: ``core`` imports nothing external), so any adapter or
pipeline can depend on these without dragging in pydantic, httpx, libsql, or torch.
"""

from __future__ import annotations

from dataclasses import dataclass

type Vector = tuple[float, ...]
"""An embedding: an ordered, immutable sequence of floats.

Its length is the embedding model's dimension (1024 for bge-m3) — a *config* value,
never baked into the type. ``tuple`` (not ``list``) keeps it immutable and hashable so
it nests cleanly inside the frozen dataclasses below.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class Page:
    """One page (or the sole page of a non-paged file) of a parsed document."""

    number: int  # 1-based; the citation unit. Non-paged formats emit a single Page(number=1).
    text: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Document:
    """A parsed source file: its identity, dedup hash, and page-segmented text."""

    path: str  # source path → becomes Source.path
    content_hash: str  # sha256 hex of the raw bytes → manifest + dedup; set by the Parser
    pages: tuple[Page, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    """An embeddable unit of a document.

    Carries everything the store needs to persist and later cite it. ``vector`` is None
    until the ingest pipeline fills it after embedding (via ``dataclasses.replace``).
    """

    text: str  # embedded; carried into Hit; summarized by the recap
    source_path: str  # denormalized from Document.path (chunks travel detached from their doc)
    page: int  # citation page
    source_hash: str  # parent file hash → known_hashes / manifest
    index: int  # 0-based ordinal within the document; (source_hash, index) is a stable PK
    vector: Vector | None = None  # None pre-embed; asserted non-None at upsert


@dataclass(frozen=True, slots=True, kw_only=True)
class Hit:
    """A retrieval result: a chunk's text plus its relevance score and citation.

    ``score`` holds cosine similarity after vector search and is replaced by the
    cross-encoder score after reranking. ``text`` is required so the reranker can score
    the (query, passage) pair and the recap can summarize it.
    """

    text: str
    score: float
    source_path: str  # → Source.path
    page: int  # → Source.page
    source_hash: str = ""
    index: int = -1


@dataclass(frozen=True, slots=True, kw_only=True)
class DocumentInfo:
    """One ingested source file, aggregated from its chunks (one row per source_hash)."""

    source_path: str
    source_hash: str
    chunks: int
