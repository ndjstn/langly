"""Simple in-memory cache for harness runs."""
from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass
class CacheEntry:
    value: dict[str, Any]
    created_at: float


class HarnessCache:
    def __init__(self, max_entries: int = 128, ttl_seconds: int = 60) -> None:
        self.max_entries = max(1, max_entries)
        self.ttl_seconds = max(1, ttl_seconds)
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()

    def get(self, key: str) -> dict[str, Any] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry.created_at > self.ttl_seconds:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return entry.value

    def set(self, key: str, value: dict[str, Any]) -> None:
        self._store[key] = CacheEntry(value=value, created_at=time.time())
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)


_HARNESS_CACHE: HarnessCache | None = None


def get_harness_cache(max_entries: int, ttl_seconds: int) -> HarnessCache:
    global _HARNESS_CACHE
    if _HARNESS_CACHE is None:
        _HARNESS_CACHE = HarnessCache(max_entries=max_entries, ttl_seconds=ttl_seconds)
    else:
        _HARNESS_CACHE.max_entries = max_entries
        _HARNESS_CACHE.ttl_seconds = ttl_seconds
    return _HARNESS_CACHE
