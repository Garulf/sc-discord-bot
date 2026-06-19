from __future__ import annotations

from typing import Any

from src.uex_api._common import CatalogResource
from src.uex_api.models import Terminal


class Terminals(CatalogResource[Terminal]):
    endpoint = "terminals"
    model = Terminal
    noun = "terminal"

    async def all(
        self,
        *,
        terminal_type: str | None = None,
        id_star_system: int | None = None,
    ) -> list[Terminal]:
        params: dict[str, Any] = {}
        if terminal_type is not None:
            params["type"] = terminal_type
        if id_star_system is not None:
            params["id_star_system"] = id_star_system
        data = await self._client.get(self.endpoint, params=params or None, cache_ttl=self._cache_ttl)
        return self._parse_rows(data)

    def _haystack(self, item: Terminal) -> str:
        return f"{item.name} {item.nickname or ''} {item.code or ''}".lower()

    def _exact_match(self, item: Terminal, needle: str) -> bool:
        return item.name.lower() == needle or (item.nickname or "").lower() == needle
