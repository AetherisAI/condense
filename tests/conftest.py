"""Shared fixtures for the contract test-suite."""

from __future__ import annotations

import pytest

from sift.adapters.embedding.fake import FakeEmbedder
from sift.adapters.store.fake import FakeVectorStore

# A small embedding dimension keeps the deterministic fakes fast and readable in tests.
TEST_DIM = 16


@pytest.fixture
def dim() -> int:
    return TEST_DIM


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder(dim=TEST_DIM)


@pytest.fixture
def store() -> FakeVectorStore:
    return FakeVectorStore()
