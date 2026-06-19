from __future__ import annotations

from typing import Any

import aiohttp

from src.http_cache import DEFAULT_CACHE_TTL_SECONDS, TTLCache, cache_key

API_BASE_URL = "https://api.uexcorp.space/2.0"
DEFAULT_TIMEOUT_SECONDS = 15
USER_AGENT = "sc-discord-bot (+https://uexcorp.space)"

ERROR_BODY_PREVIEW = 200


class UEXError(Exception):
    pass


class NotFoundError(UEXError):
    pass


class APIStatusError(UEXError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"UEX API returned HTTP {status}: {message}")
        self.status = status


class UEXClient:
    def __init__(
        self,
        base_url: str = API_BASE_URL,
        *,
        token: str | None = None,
        session: aiohttp.ClientSession | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
        cache: Any | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._external_session = session
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._cache = cache if cache is not None else TTLCache(cache_ttl)

    async def __aenter__(self) -> UEXClient:
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
        params: dict[str, Any] | None = None,
        cache_ttl: float | None = None,
    ) -> Any:
        use_cache = cache_ttl is None or cache_ttl > 0
        if not use_cache:
            return await self._fetch(path, params)

        key = cache_key(path, params)
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

    async def _fetch(self, path: str, params: dict[str, Any] | None) -> Any:
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
            raise APIStatusError(response.status, body[:ERROR_BODY_PREVIEW])

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
