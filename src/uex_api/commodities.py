from __future__ import annotations

from src.uex_api._common import CatalogResource
from src.uex_api.models import Commodity


class Commodities(CatalogResource[Commodity]):
    endpoint = "commodities"
    model = Commodity
    noun = "commodity"

    def _haystack(self, item: Commodity) -> str:
        return f"{item.name} {item.code or ''}".lower()

    def _exact_match(self, item: Commodity, needle: str) -> bool:
        return item.name.lower() == needle or (item.code or "").lower() == needle
