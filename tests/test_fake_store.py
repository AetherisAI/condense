from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore
from sift.core.types import Chunk


def _chunk(cid, text, emb, tenant="default"):
    return Chunk(id=cid, text=text, path=f"/{cid}.md", page=None,
                 content_hash=cid, tenant=tenant, embedding=emb)


def test_search_ranks_by_cosine_and_filters_tenant():
    e = FakeEmbedder()
    store = FakeVectorStore()
    store.ensure_ready("bge-m3", 1024)
    store.upsert([
        _chunk("a", "apple", e.embed(["apple"])[0]),
        _chunk("b", "banana", e.embed(["banana"])[0]),
        _chunk("c", "other", e.embed(["apple"])[0], tenant="t2"),  # different tenant
    ])
    hits = store.search(e.embed(["apple"])[0], k=2, tenant="default")
    assert hits[0].id == "a"                       # best match first
    assert all(h.id != "c" for h in hits)          # tenant filtered out


def test_known_hashes():
    store = FakeVectorStore()
    store.upsert([_chunk("a", "x", [0.0] * 1024)])
    assert store.known_hashes("default") == {"a"}
