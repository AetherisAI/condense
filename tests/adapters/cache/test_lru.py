"""Tests for :class:`~sift.adapters.cache.lru.LruCache`, the bounded map behind the query caches."""

from __future__ import annotations

import pytest

from sift.adapters.cache.lru import LruCache


def test_get_returns_what_was_put() -> None:
    cache: LruCache[str, int] = LruCache(4)
    cache.put("a", 1)

    assert cache.get("a") == 1
    assert cache.get("missing") is None
    assert len(cache) == 1


def test_oldest_entry_is_evicted_when_full() -> None:
    cache: LruCache[str, int] = LruCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert len(cache) == 2


def test_get_makes_an_entry_the_most_recent() -> None:
    cache: LruCache[str, int] = LruCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")  # "b" is now the least recently used
    cache.put("c", 3)

    assert cache.get("a") == 1
    assert cache.get("b") is None


def test_put_on_an_existing_key_replaces_it_without_growing() -> None:
    cache: LruCache[str, int] = LruCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)  # "b" is now the least recently used
    cache.put("c", 3)

    assert cache.get("a") == 10
    assert cache.get("b") is None
    assert len(cache) == 2


def test_counts_hits_and_misses() -> None:
    cache: LruCache[str, int] = LruCache(2)
    cache.put("a", 1)
    cache.get("a")
    cache.get("a")
    cache.get("b")

    assert (cache.hits, cache.misses) == (2, 1)


def test_rejects_a_size_below_one() -> None:
    with pytest.raises(ValueError):
        LruCache(0)
