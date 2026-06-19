"""A tiny async in-memory cache shared by the API clients.

Both the star-citizen.wiki and UEX clients cache GET responses for a short
while: the underlying catalogue data changes rarely, so caching spares the
remote API repeated identical calls (especially from autocomplete). Keeping the
implementation here means there is a single source of truth instead of a copy in
each client package.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

DEFAULT_CACHE_TTL_SECONDS = 300


class TTLCache:
    """An in-memory cache with per-entry expiry and per-key locking.

    The per-key lock lets concurrent callers asking for the same thing share a
    single in-flight request instead of stampeding the API.
    """

    def __init__(self, ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._entries: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            del self._entries[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        lifetime = self._ttl if ttl is None else ttl
        self._entries[key] = (time.monotonic() + lifetime, value)

    def lock(self, key: str) -> asyncio.Lock:
        existing = self._locks.get(key)
        if existing is not None:
            return existing
        created = asyncio.Lock()
        self._locks[key] = created
        return created

    async def clear(self) -> None:
        self._entries.clear()


def cache_key(path: str, params: dict[str, Any] | None) -> str:
    """Build a stable cache key from a request path and its query params."""
    if not params:
        return path
    ordered = sorted((str(name), str(value)) for name, value in params.items())
    encoded = "&".join(f"{name}={value}" for name, value in ordered)
    return f"{path}?{encoded}"
