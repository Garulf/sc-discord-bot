from __future__ import annotations

from typing import Any, Optional

from src.uex_api.client import NotFoundError, UEXClient
from src.uex_api.models import Terminal

DEFAULT_CACHE_TTL_SECONDS = 3600


class Terminals:
    def __init__(self, client: UEXClient, *, cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl

    async def all(
        self,
        *,
        terminal_type: Optional[str] = None,
        id_star_system: Optional[int] = None,
    ) -> list[Terminal]:
        params: dict[str, Any] = {}
        if terminal_type is not None:
            params["type"] = terminal_type
        if id_star_system is not None:
            params["id_star_system"] = id_star_system
        data = await self._client.get(
            "terminals", params=params or None, cache_ttl=self._cache_ttl
        )
        rows: list[Any] = data if isinstance(data, list) else []
        return [Terminal.from_api(row) for row in rows if isinstance(row, dict)]

    async def get(self, terminal_id: int) -> Terminal:
        for terminal in await self.all():
            if terminal.id == terminal_id:
                return terminal
        raise NotFoundError(f"No terminal with id {terminal_id}")

    async def search(self, query: str, *, limit: int = 25) -> list[Terminal]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[Terminal] = []
        for terminal in await self.all():
            haystack = f"{terminal.name} {terminal.nickname or ''} {terminal.code or ''}".lower()
            if needle in haystack:
                matches.append(terminal)
            if len(matches) >= limit:
                break
        return matches

    async def find(self, query: str) -> Optional[Terminal]:
        results = await self.search(query, limit=25)
        if not results:
            return None
        needle = query.strip().lower()
        for terminal in results:
            if terminal.name.lower() == needle:
                return terminal
            if (terminal.nickname or "").lower() == needle:
                return terminal
        return results[0]
