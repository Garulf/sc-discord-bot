from __future__ import annotations

from src.uex_api._common import CatalogResource
from src.uex_api.models import Vehicle


class Vehicles(CatalogResource[Vehicle]):
    endpoint = "vehicles"
    model = Vehicle
    noun = "vehicle"

    def _haystack(self, item: Vehicle) -> str:
        return f"{item.name} {item.name_full or ''}".lower()

    def _exact_match(self, item: Vehicle, needle: str) -> bool:
        return item.name.lower() == needle or (item.name_full or "").lower() == needle
