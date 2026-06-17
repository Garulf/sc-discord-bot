from __future__ import annotations

from typing import Any, Optional

from src.uex_api.client import NotFoundError, UEXClient
from src.uex_api.models import Commodity

DEFAULT_CACHE_TTL_SECONDS = 3600


class Commodities:
    def __init__(self, client: UEXClient, *, cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl

    async def all(self) -> list[Commodity]:
        data = await self._client.get("commodities", cache_ttl=self._cache_ttl)
        rows: list[Any] = data if isinstance(data, list) else []
        return [Commodity.from_api(row) for row in rows if isinstance(row, dict)]

    async def get(self, commodity_id: int) -> Commodity:
        for commodity in await self.all():
            if commodity.id == commodity_id:
                return commodity
        raise NotFoundError(f"No commodity with id {commodity_id}")

    async def search(self, query: str, *, limit: int = 25) -> list[Commodity]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[Commodity] = []
        for commodity in await self.all():
            haystack = f"{commodity.name} {commodity.code or ''}".lower()
            if needle in haystack:
                matches.append(commodity)
            if len(matches) >= limit:
                break
        return matches

    async def find(self, query: str) -> Optional[Commodity]:
        results = await self.search(query, limit=25)
        if not results:
            return None
        needle = query.strip().lower()
        for commodity in results:
            if commodity.name.lower() == needle:
                return commodity
            if (commodity.code or "").lower() == needle:
                return commodity
        return results[0]
