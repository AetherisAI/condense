"""Pure domain types — ZERO external deps (dependency rule: core imports nothing)."""
from __future__ import annotations

from dataclasses import dataclass

Vector = list[float]          # dense embedding; bge-m3 => length 1024
EMBED_DIM = 1024


@dataclass(frozen=True)
class Page:
    number: int
    text: str


@dataclass(frozen=True)
class Document:
    path: str
    pages: list[Page]
    content_hash: str


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    path: str
    page: int | None
    content_hash: str
    tenant: str
    embedding: Vector | None = None


@dataclass(frozen=True)
class Hit:
    id: str
    text: str
    path: str
    page: int | None
    score: float
