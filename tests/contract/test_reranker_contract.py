"""Contract tests for the Reranker port, via NullReranker (identity)."""

from __future__ import annotations

from sift.adapters.rerank.null import NullReranker
from sift.core.ports import Reranker
from sift.core.types import Hit


def _hit(text: str, score: float) -> Hit:
    return Hit(text=text, score=score, source_path=f"{text}.md", page=1)


def test_null_reranker_satisfies_port() -> None:
    impl: Reranker = NullReranker()
    assert isinstance(impl, Reranker)


async def test_preserves_order_and_does_not_mutate() -> None:
    reranker = NullReranker()
    candidates = [_hit("a", 0.9), _hit("b", 0.5), _hit("c", 0.1)]
    snapshot = list(candidates)

    out = await reranker.rerank("query", candidates)

    assert out == snapshot  # same items, same order
    assert candidates == snapshot  # input not mutated
    assert out is not candidates  # fresh list, no aliasing
