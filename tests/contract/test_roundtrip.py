"""End-to-end proof that the ports *compose* with zero real adapters.

ingest (ensure_ready → embed → upsert) then search (embed → retrieve wide → rerank →
take FINAL_K), wired from only the three Step-0 fakes. The fake embedder matches on exact
text (it is not semantic), so the query reuses a corpus entry verbatim to retrieve it.
"""

from __future__ import annotations

from dataclasses import replace

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.rerank.null import NullReranker
from sift.adapters.store.fake import FakeVectorStore
from sift.core.types import Chunk

CORPUS = [
    "the mitochondria is the powerhouse of the cell",
    "the sky appears blue because of rayleigh scattering",
    "espresso is brewed by forcing hot water through coffee grounds",
]


async def test_fakes_compose_end_to_end() -> None:
    tenant = "default"
    model, dim = "bge-m3", 32
    retrieve_k, final_k = 30, 1

    embedder = FakeEmbedder(dim=dim)
    store = FakeVectorStore()
    reranker = NullReranker()

    # --- ingest: ensure_ready → embed → upsert ---
    await store.ensure_ready(model, dim, tenant)
    chunks = [
        Chunk(text=text, source_path=f"doc{i}.md", page=1, source_hash=f"h{i}", index=0)
        for i, text in enumerate(CORPUS)
    ]
    vectors = await embedder.embed([c.text for c in chunks])
    embedded = [replace(c, vector=v) for c, v in zip(chunks, vectors, strict=True)]
    await store.upsert(embedded, tenant)

    # --- search: embed → retrieve wide → rerank → take FINAL_K ---
    query = CORPUS[1]  # exact-match query → deterministically the best hit
    (query_vec,) = await embedder.embed([query])
    candidates = await store.search(query_vec, retrieve_k, tenant)
    ranked = await reranker.rerank(query, candidates)
    best = ranked[:final_k]

    assert len(best) == final_k
    assert best[0].source_path == "doc1.md"
    assert best[0].page == 1
