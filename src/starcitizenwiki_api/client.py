"""A small async client for the star-citizen.wiki REST API.

Docs: https://docs.star-citizen.wiki/ (Swagger UI for the v2 API)

The client is intentionally generic: it only knows how to talk HTTP to the API
base URL and turn responses into JSON, raising typed errors on failure. Each
resource (ships, components, ...) builds on top of it.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from src.http_cache import DEFAULT_CACHE_TTL_SECONDS, TTLCache, cache_key

API_BASE_URL = "https://api.star-citizen.wiki/api/v2"
DEFAULT_TIMEOUT_SECONDS = 15
USER_AGENT = "sc-discord-bot (+https://github.com/StarCitizenWiki/API)"

ERROR_BODY_PREVIEW = 200


class StarCitizenWikiError(Exception):
    """Base class for every error raised by the API client."""


class NotFoundError(StarCitizenWikiError):
    """The requested resource does not exist (HTTP 404)."""


class APIStatusError(StarCitizenWikiError):
    """The API responded with an unexpected non-2xx status."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"API returned HTTP {status}: {message}")
        self.status = status


class StarCitizenWikiClient:
    """Async HTTP client for the star-citizen.wiki API.

    Either pass in an existing :class:`aiohttp.ClientSession` (the client will
    not close it for you) or let the client lazily create and own one. When the
    client owns the session, use it as an async context manager or remember to
    ``await client.close()`` during shutdown.
    """

    def __init__(
        self,
        base_url: str = API_BASE_URL,
        *,
        session: aiohttp.ClientSession | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        locale: str | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS,
        cache: Any | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._external_session = session
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._locale = locale
        self._cache = cache if cache is not None else TTLCache(cache_ttl)

    async def __aenter__(self) -> StarCitizenWikiClient:
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        # Created lazily so the session binds to the running event loop rather
        # than whatever loop happened to exist at construction time.
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
        return self._session

    async def close(self) -> None:
        """Close the underlying session, unless it was supplied by the caller."""
        if self._external_session is None and self._session is not None and not self._session.closed:
            await self._session.close()

    def _merge_locale(self, params: dict[str, Any] | None) -> dict[str, Any]:
        query = dict(params or {})
        if self._locale and "locale" not in query:
            query["locale"] = self._locale
        return query

    async def clear_cache(self) -> None:
        """Drop every cached GET response."""
        await self._cache.clear()

    async def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        cache_ttl: float | None = None,
    ) -> Any:
        """GET ``{base_url}/{path}`` and return the decoded JSON body.

        Successful responses are cached; pass ``cache_ttl=0`` to bypass the
        cache for a single call, or a number to override the default lifetime.
        """
        query = self._merge_locale(params)
        use_cache = cache_ttl is None or cache_ttl > 0
        if not use_cache:
            return await self._request("GET", path, params=query)

        key = cache_key(path, query)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached

        lock = self._cache.lock(key)
        async with lock:
            cached = await self._cache.get(key)
            if cached is not None:
                return cached
            data = await self._request("GET", path, params=query)
            await self._cache.set(key, data, cache_ttl)
            return data

    async def post(
        self,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """POST to ``{base_url}/{path}`` and return the decoded JSON body."""
        return await self._request("POST", path, json=json, params=self._merge_locale(params))

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        session = await self._ensure_session()
        url = path if path.startswith("http://") or path.startswith("https://") else f"{self._base_url}/{path.lstrip('/')}"
        try:
            async with session.request(method, url, params=params, json=json) as response:
                if response.status == 404:
                    raise NotFoundError(f"{url} returned 404")
                if response.status >= 400:
                    body = await response.text()
                    raise APIStatusError(response.status, body[:ERROR_BODY_PREVIEW])
                return await response.json()
        except aiohttp.ClientError as e:
            raise StarCitizenWikiError(f"Request to {url} failed: {e}") from e
