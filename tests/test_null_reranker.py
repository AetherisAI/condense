from sift.adapters.rerank.null import NullReranker
from sift.core.types import Hit


def test_null_reranker_preserves_order():
    hits = [Hit(id=str(i), text="t", path="/p", page=None, score=1.0 - i / 10) for i in range(3)]
    assert NullReranker().rerank("q", hits) == hits
