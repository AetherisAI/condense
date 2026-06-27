from sift.core.types import Vector, EMBED_DIM, Page, Document, Chunk, Hit


def test_embed_dim_is_1024():
    assert EMBED_DIM == 1024


def test_hit_and_chunk_construct():
    h = Hit(id="1", text="x", path="/a.md", page=2, score=0.9)
    assert h.path == "/a.md" and h.page == 2
    c = Chunk(id="1", text="x", path="/a.md", page=2, content_hash="ab", tenant="default")
    assert c.embedding is None and c.tenant == "default"


def test_document_holds_pages():
    d = Document(path="/a.md", pages=[Page(number=1, text="hi")], content_hash="ab")
    assert d.pages[0].text == "hi"
