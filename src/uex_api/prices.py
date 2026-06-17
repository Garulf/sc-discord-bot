from __future__ import annotations

from typing import Any, Optional

from src.uex_api.client import UEXClient
from src.uex_api.models import CommodityPrice

DEFAULT_CACHE_TTL_SECONDS = 60


class CommodityPrices:
    def __init__(self, client: UEXClient, *, cache_ttl: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl

    async def for_terminal(self, id_terminal: int) -> list[CommodityPrice]:
        return await self._query({"id_terminal": id_terminal})

    async def for_commodity(self, id_commodity: int) -> list[CommodityPrice]:
        return await self._query({"id_commodity": id_commodity})

    async def all(self) -> list[CommodityPrice]:
        data = await self._client.get("commodities_prices_all", cache_ttl=self._cache_ttl)
        rows: list[Any] = data if isinstance(data, list) else []
        return [CommodityPrice.from_api(row) for row in rows if isinstance(row, dict)]

    async def best_sell(self, id_commodity: int) -> Optional[CommodityPrice]:
        sellable = [p for p in await self.for_commodity(id_commodity) if p.price_sell]
        if not sellable:
            return None
        sellable.sort(key=lambda price: price.price_sell or 0.0, reverse=True)
        return sellable[0]

    async def best_buy(self, id_commodity: int) -> Optional[CommodityPrice]:
        buyable = [p for p in await self.for_commodity(id_commodity) if p.price_buy]
        if not buyable:
            return None
        buyable.sort(key=lambda price: price.price_buy or float("inf"))
        return buyable[0]

    async def _query(self, params: dict[str, Any]) -> list[CommodityPrice]:
        data = await self._client.get(
            "commodities_prices", params=params, cache_ttl=self._cache_ttl
        )
        rows: list[Any] = data if isinstance(data, list) else []
        return [CommodityPrice.from_api(row) for row in rows if isinstance(row, dict)]
