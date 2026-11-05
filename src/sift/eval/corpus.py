"""Read-only access to the ingested corpus, through the public toolbox (never the store).

``validate``, ``bootstrap`` and the noise sweep all need "which documents exist" and "give me
this document's chunks" — the toolbox's ``list_documents``/``get_document_chunks`` already do
exactly that, including ``ensure_ready`` (model-pin check, schema migration), so the eval goes
through :class:`~sift.pipelines.tools.ToolRegistry` like any other consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

from sift.eval.matching import path_matches
from sift.eval.records import Passage
from sift.factory import Container

_PAGE = 500


@dataclass(frozen=True, slots=True, kw_only=True)
class Doc:
    path: str
    source_hash: str
    chunks: int


async def list_documents(container: Container, tenant: str) -> list[Doc]:
    docs: list[Doc] = []
    offset = 0
    while True:
        page = await container.tools.call(
            "list_documents", {"limit": _PAGE, "offset": offset}, tenant
        )
        rows = page.get("documents", [])
        docs.extend(
            Doc(path=d.source_path, source_hash=d.source_hash, chunks=d.chunks) for d in rows
        )
        offset += len(rows)
        if not rows or offset >= page.get("total", 0):
            return docs


async def document_passages(container: Container, source_hash: str, tenant: str) -> list[Passage]:
    chunks = await container.tools.call("get_document_chunks", {"source_hash": source_hash}, tenant)
    return [
        Passage(
            path=c.source_path,
            page=c.page,
            text=c.text,
            source_hash=c.source_hash,
            index=c.index,
        )
        for c in chunks
    ]


def resolve(gold_path: str, docs: list[Doc]) -> list[Doc]:
    """Every ingested document a gold path matches (exactly one is the healthy case)."""
    return [d for d in docs if path_matches(d.path, gold_path)]
