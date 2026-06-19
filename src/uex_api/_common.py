"""Shared building blocks for the UEX resource modules.

The catalogue endpoints (commodities, vehicles, terminals) all fetch a full list
and then search it in memory the same way; :class:`CatalogResource` captures that
shared shape so each resource only declares its endpoint, model, and which fields
to match on.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from src.uex_api.client import NotFoundError, UEXClient

# Cache lifetimes in seconds. Catalogue/reference data (commodities, vehicles,
# terminals, star systems) changes rarely, so it is cached for an hour. Live
# market data moves constantly, so it is cached only briefly.
CATALOGUE_CACHE_TTL_SECONDS = 3600
COMMODITY_PRICE_CACHE_TTL_SECONDS = 60
VEHICLE_PRICE_CACHE_TTL_SECONDS = 300

DEFAULT_SEARCH_LIMIT = 25

ModelT = TypeVar("ModelT")


class CatalogResource(Generic[ModelT]):
    """Base for a UEX catalogue endpoint: list ``all``, ``get`` by id, ``search``, ``find``.

    Subclasses set ``endpoint`` (the API path), ``model`` (the dataclass with a
    ``from_api`` parser and an ``id``/``name``), and ``noun`` (used in not-found
    messages). They override :meth:`_haystack` and :meth:`_exact_match` to control
    which fields a query is matched against.
    """

    endpoint: str
    model: type[ModelT]
    noun: str

    def __init__(self, client: UEXClient, *, cache_ttl: float = CATALOGUE_CACHE_TTL_SECONDS) -> None:
        self._client = client
        self._cache_ttl = cache_ttl

    async def all(self) -> list[ModelT]:
        data = await self._client.get(self.endpoint, cache_ttl=self._cache_ttl)
        return self._parse_rows(data)

    def _parse_rows(self, data: Any) -> list[ModelT]:
        rows: list[Any] = data if isinstance(data, list) else []
        return [self.model.from_api(row) for row in rows if isinstance(row, dict)]

    async def get(self, item_id: int) -> ModelT:
        for item in await self.all():
            if item.id == item_id:
                return item
        raise NotFoundError(f"No {self.noun} with id {item_id}")

    async def search(self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[ModelT]:
        needle = query.strip().lower()
        if not needle:
            return []
        matches: list[ModelT] = []
        for item in await self.all():
            if needle in self._haystack(item):
                matches.append(item)
            if len(matches) >= limit:
                break
        return matches

    async def find(self, query: str) -> ModelT | None:
        results = await self.search(query, limit=DEFAULT_SEARCH_LIMIT)
        if not results:
            return None
        needle = query.strip().lower()
        for item in results:
            if self._exact_match(item, needle):
                return item
        return results[0]

    def _haystack(self, item: ModelT) -> str:
        """The lowercased text a search query is tested against."""
        return item.name.lower()

    def _exact_match(self, item: ModelT, needle: str) -> bool:
        """Whether ``item`` is an exact match for an already-lowercased query."""
        return item.name.lower() == needle
