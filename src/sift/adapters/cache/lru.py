"""A bounded least-recently-used map, the storage behind the query-time caches.

Every key the caches use is derived from content (a query's text, or a query plus a passage's
text), so an entry can never go stale and nothing is ever invalidated: once the cache is full,
the least recently used entry is dropped.

There is no lock. The engine runs on one asyncio event loop and every method here is
synchronous, so two callers can never interleave inside one. Two concurrent searches for the
same new query may both miss and both fetch; the second ``put`` stores the same value again.
"""

from __future__ import annotations

from collections import OrderedDict


class LruCache[K, V]:
    """Holds up to ``max_entries`` items; reading or writing an item makes it the most recent.

    ``get`` returns ``None`` for a missing key, so values must never be ``None`` themselves.
    ``hits`` and ``misses`` count ``get`` outcomes, for tests and debugging.
    """

    def __init__(self, max_entries: int) -> None:
        if max_entries < 1:
            raise ValueError(f"max_entries must be at least 1, got {max_entries}")
        self._max_entries = max_entries
        self._items: OrderedDict[K, V] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: K) -> V | None:
        try:
            value = self._items[key]
        except KeyError:
            self.misses += 1
            return None
        self._items.move_to_end(key)
        self.hits += 1
        return value

    def put(self, key: K, value: V) -> None:
        self._items[key] = value
        self._items.move_to_end(key)
        if len(self._items) > self._max_entries:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)
