from sift.core.ports import Embedder
from sift.core.types import Vector


class _Stub:
    def embed(self, texts: list[str]) -> list[Vector]:
        return [[0.0] for _ in texts]


def test_stub_is_structural_embedder():
    e: Embedder = _Stub()          # passes pyright structurally
    assert e.embed(["a", "b"]) == [[0.0], [0.0]]
