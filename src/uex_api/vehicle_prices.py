from __future__ import annotations

from typing import Any

from src.uex_api.client import UEXClient
from src.uex_api.models import VehiclePurchasePrice, VehicleRentalPrice

DEFAULT_CACHE_TTL_SECONDS = 300


class VehiclePrices:
    def __init__(self, client: UEXClient, *, cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl

    async def purchases_for_vehicle(self, id_vehicle: int) -> list[VehiclePurchasePrice]:
        rows = await self._query("vehicles_purchases_prices", {"id_vehicle": id_vehicle})
        return [VehiclePurchasePrice.from_api(row) for row in rows]

    async def purchases_for_terminal(self, id_terminal: int) -> list[VehiclePurchasePrice]:
        rows = await self._query("vehicles_purchases_prices", {"id_terminal": id_terminal})
        return [VehiclePurchasePrice.from_api(row) for row in rows]

    async def cheapest_purchase(self, id_vehicle: int) -> VehiclePurchasePrice | None:
        priced = [p for p in await self.purchases_for_vehicle(id_vehicle) if p.price_buy]
        if not priced:
            return None
        priced.sort(key=lambda price: price.price_buy or float("inf"))
        return priced[0]

    async def rentals_for_vehicle(self, id_vehicle: int) -> list[VehicleRentalPrice]:
        rows = await self._query("vehicles_rentals_prices", {"id_vehicle": id_vehicle})
        return [VehicleRentalPrice.from_api(row) for row in rows]

    async def cheapest_rental(self, id_vehicle: int) -> VehicleRentalPrice | None:
        priced = [p for p in await self.rentals_for_vehicle(id_vehicle) if p.price_rent]
        if not priced:
            return None
        priced.sort(key=lambda price: price.price_rent or float("inf"))
        return priced[0]

    async def _query(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        data = await self._client.get(path, params=params, cache_ttl=self._cache_ttl)
        rows: list[Any] = data if isinstance(data, list) else []
        return [row for row in rows if isinstance(row, dict)]
