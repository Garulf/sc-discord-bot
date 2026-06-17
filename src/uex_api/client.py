from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import aiohttp

API_BASE_URL = "https://api.uexcorp.space/2.0"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_CACHE_TTL_SECONDS = 300
USER_AGENT = "sc-discord-bot (+https://uexcorp.space)"


class UEXError(Exception):
    pass


class NotFoundError(UEXError):
    pass


class APIStatusError(UEXError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"UEX API returned HTTP {status}: {message}")
        self.status = status


class TTLCache:
    def __init__(self, ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._entries: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def get(self, key: str) -> Optional[Any]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at < time.monotonic():
            del self._entries[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
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


class UEXClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        *,
        token: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
        cache: Optional[Any] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._external_session = session
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._cache = cache if cache is not None else TTLCache(cache_ttl)

    async def __aenter__(self) -> "UEXClient":
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout, headers=self._headers())
        return self._session

    async def close(self) -> None:
        if self._external_session is not None:
            return
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def clear_cache(self) -> None:
        await self._cache.clear()

    async def get(
        self,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        cache_ttl: Optional[float] = None,
    ) -> Any:
        use_cache = cache_ttl is None or cache_ttl > 0
        if not use_cache:
            return await self._fetch(path, params)

        key = self._cache_key(path, params)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached

        lock = self._cache.lock(key)
        async with lock:
            cached = await self._cache.get(key)
            if cached is not None:
                return cached
            data = await self._fetch(path, params)
            await self._cache.set(key, data, cache_ttl)
            return data

    def _cache_key(self, path: str, params: Optional[dict[str, Any]]) -> str:
        if not params:
            return path
        ordered = sorted((str(name), str(value)) for name, value in params.items())
        encoded = "&".join(f"{name}={value}" for name, value in ordered)
        return f"{path}?{encoded}"

    async def _fetch(self, path: str, params: Optional[dict[str, Any]]) -> Any:
        session = await self._ensure_session()
        url = f"{self._base_url}/{path.lstrip('/')}"
        try:
            async with session.get(url, params=params) as response:
                return await self._parse(response, url)
        except aiohttp.ClientError as e:
            raise UEXError(f"Request to {url} failed: {e}") from e

    async def _parse(self, response: aiohttp.ClientResponse, url: str) -> Any:
        if response.status == 404:
            raise NotFoundError(f"{url} returned 404")
        if response.status >= 400:
            body = await response.text()
            raise APIStatusError(response.status, body[:200])

        payload = await response.json()
        if not isinstance(payload, dict):
            return payload

        status = payload.get("status")
        if status is not None and status != "ok":
            message = payload.get("message") or status
            raise APIStatusError(response.status, str(message))
        if "data" in payload:
            return payload["data"]
        return payload
