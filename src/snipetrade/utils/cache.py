"""Simple TTL cache utilities used across the scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Dict, Generic, Hashable, Optional, TypeVar


K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


@dataclass
class _CacheEntry(Generic[V]):
    """Internal representation of a cached value."""

    value: V
    expires_at: datetime


class TTLCache(Generic[K, V]):
    """A lightweight thread-safe TTL cache.

    The cache keeps values for ``ttl_seconds`` seconds before considering them
    expired. Expired values are lazily purged when they are accessed. This
    avoids pulling in external dependencies such as ``cachetools`` while
    providing the small feature set we need inside the project.
    """

    def __init__(self, ttl_seconds: int = 60):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")
        self._default_ttl = ttl_seconds
        self._store: Dict[K, _CacheEntry[V]] = {}
        self._lock = RLock()

    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    def get(self, key: K) -> Optional[V]:
        """Return a cached value if it has not expired."""

        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None

            if entry.expires_at <= self._now():
                self._store.pop(key, None)
                return None

            return entry.value

    def set(self, key: K, value: V, ttl: Optional[int] = None) -> None:
        """Store ``value`` under ``key`` for ``ttl`` seconds."""

        ttl_seconds = ttl if ttl is not None else self._default_ttl
        if ttl_seconds <= 0:
            raise ValueError("ttl must be greater than zero")

        with self._lock:
            expires_at = self._now() + timedelta(seconds=ttl_seconds)
            self._store[key] = _CacheEntry(value=value, expires_at=expires_at)

    def clear(self) -> None:
        """Remove all cached items."""

        with self._lock:
            self._store.clear()

    def pop(self, key: K) -> Optional[V]:
        """Remove a cached value and return it if present."""

        with self._lock:
            entry = self._store.pop(key, None)
            return entry.value if entry else None


__all__ = ["TTLCache"]

