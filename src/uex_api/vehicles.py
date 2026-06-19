from __future__ import annotations

from typing import Any

from src.uex_api.client import NotFoundError, UEXClient
from src.uex_api.models import Vehicle

DEFAULT_CACHE_TTL_SECONDS = 3600


class Vehicles:
    def __init__(self, client: UEXClient, *, cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl

    async def all(self) -> list[Vehicle]:
        data = await self._client.get("vehicles", cache_ttl=self._cache_ttl)
        rows: list[Any] = data if isinstance(data, list) else []
        return [Vehicle.from_api(row) for row in rows if isinstance(row, dict)]

    async def get(self, vehicle_id: int) -> Vehicle:
        for vehicle in await self.all():
            if vehicle.id == vehicle_id:
                return vehicle
        raise NotFoundError(f"No vehicle with id {vehicle_id}")

    async def search(self, query: str, *, limit: int = 25) -> list[Vehicle]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[Vehicle] = []
        for vehicle in await self.all():
            haystack = f"{vehicle.name} {vehicle.name_full or ''}".lower()
            if needle in haystack:
                matches.append(vehicle)
            if len(matches) >= limit:
                break
        return matches

    async def find(self, query: str) -> Vehicle | None:
        results = await self.search(query, limit=25)
        if not results:
            return None
        needle = query.strip().lower()
        for vehicle in results:
            if vehicle.name.lower() == needle:
                return vehicle
            if (vehicle.name_full or "").lower() == needle:
                return vehicle
        return results[0]
