"""Ports — the interfaces everything codes against. Stdlib only."""
from __future__ import annotations

from typing import Protocol

from .types import Chunk, Document, Hit, Vector


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[Vector]: ...


class Reranker(Protocol):
    def rerank(self, query: str, candidates: list[Hit]) -> list[Hit]: ...


class Completer(Protocol):
    def complete(self, system: str, user: str) -> str: ...


class VectorStore(Protocol):
    def ensure_ready(self, model: str, dim: int) -> None: ...
    def upsert(self, chunks: list[Chunk]) -> None: ...
    def search(self, vector: Vector, k: int, tenant: str) -> list[Hit]: ...
    def known_hashes(self, tenant: str) -> set[str]: ...


class Parser(Protocol):
    def parse(self, data: bytes, filename: str) -> Document: ...


class Chunker(Protocol):
    def chunk(self, doc: Document) -> list[Chunk]: ...
