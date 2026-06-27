"""Contract tests for the Embedder port, via FakeEmbedder."""

from __future__ import annotations

import math

from sift.adapters.embedding.fake import FakeEmbedder
from sift.core.ports import Embedder
from sift.core.types import Vector


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b)


def test_fake_embedder_satisfies_port() -> None:
    impl: Embedder = FakeEmbedder()
    assert isinstance(impl, Embedder)


async def test_embeds_each_text_to_configured_dim(embedder: FakeEmbedder, dim: int) -> None:
    out = await embedder.embed(["alpha", "beta", "gamma"])
    assert len(out) == 3
    assert all(len(vec) == dim for vec in out)


async def test_is_deterministic_across_instances(dim: int) -> None:
    a = await FakeEmbedder(dim=dim).embed(["same text"])
    b = await FakeEmbedder(dim=dim).embed(["same text"])
    assert a == b


async def test_distinct_texts_give_distinct_vectors(embedder: FakeEmbedder) -> None:
    va, vb = await embedder.embed(["one", "two"])
    assert va != vb


async def test_identical_text_is_self_similar(embedder: FakeEmbedder) -> None:
    (vec,) = await embedder.embed(["hello world"])
    assert math.isclose(_cosine(vec, vec), 1.0, rel_tol=1e-9)
