import math

from sift.adapters.embedding.fake import FakeEmbedder
from sift.core.types import EMBED_DIM


def test_deterministic_and_dim():
    e = FakeEmbedder()
    a1, a2 = e.embed(["alpha"])[0], e.embed(["alpha"])[0]
    assert a1 == a2 and len(a1) == EMBED_DIM


def test_unit_norm_and_distinct():
    e = FakeEmbedder()
    a, b = e.embed(["alpha"])[0], e.embed(["beta"])[0]
    assert abs(math.sqrt(sum(x * x for x in a)) - 1.0) < 1e-9
    assert a != b
