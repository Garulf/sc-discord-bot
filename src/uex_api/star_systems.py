from __future__ import annotations

from typing import Any

from src.uex_api._common import CATALOGUE_CACHE_TTL_SECONDS
from src.uex_api.client import NotFoundError, UEXClient
from src.uex_api.models import StarSystem


class StarSystems:
    def __init__(self, client: UEXClient, *, cache_ttl: float = CATALOGUE_CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl

    async def all(self) -> list[StarSystem]:
        data = await self._client.get("star_systems", cache_ttl=self._cache_ttl)
        rows: list[Any] = data if isinstance(data, list) else []
        return [StarSystem.from_api(row) for row in rows if isinstance(row, dict)]

    async def get(self, star_system_id: int) -> StarSystem:
        for system in await self.all():
            if system.id == star_system_id:
                return system
        raise NotFoundError(f"No star system with id {star_system_id}")

    async def find(self, query: str) -> StarSystem | None:
        needle = query.strip().lower()
        if not needle:
            return None
        systems = await self.all()
        for system in systems:
            if system.name.lower() == needle:
                return system
            if (system.code or "").lower() == needle:
                return system
        for system in systems:
            if needle in system.name.lower():
                return system
        return None
