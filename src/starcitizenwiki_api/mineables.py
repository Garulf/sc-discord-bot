"""Star Citizen Wiki API module for mineable resources.

The commodity list endpoint does not support server-side name filtering, so
this module fetches both pages on first use, filters to mineables in-memory,
and keeps the result for the process lifetime. Individual item fetches go
through the standard client cache (SQLite TTL).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api._common import extract_data, first_image
from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient

_ENDPOINT = "commodities"
_PAGE_SIZE = 200


@dataclass(frozen=True)
class MineableSummary:
    name: str
    slug: str
    methods: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MineableSummary:
        return cls(
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            methods=data.get("methods") or [],
        )


@dataclass(frozen=True)
class MiningLocation:
    display_name: str
    system: str
    type: str
    parent_name: str | None
    probability_percent: float | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> MiningLocation:
        return cls(
            display_name=data.get("display_name") or data.get("name", ""),
            system=data.get("system", ""),
            type=data.get("type", ""),
            parent_name=data.get("parent_name"),
            probability_percent=data.get("group_probability_percent"),
        )


@dataclass(frozen=True)
class SystemGroup:
    name: str
    locations: list[MiningLocation]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> SystemGroup:
        return cls(
            name=data.get("name", ""),
            locations=[MiningLocation.from_api(loc) for loc in (data.get("locations") or [])],
        )


@dataclass(frozen=True)
class Mineable:
    name: str
    slug: str | None
    methods: list[str]
    systems_grouped: list[SystemGroup]
    web_url: str | None
    image_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Mineable:
        return cls(
            name=data.get("name", ""),
            slug=data.get("slug"),
            methods=data.get("methods") or [],
            systems_grouped=[SystemGroup.from_api(sg) for sg in (data.get("systems_grouped") or [])],
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
        )


class Mineables:
    """API helper for mineable resources."""

    def __init__(self, client: StarCitizenWikiClient) -> None:
        self._client = client
        self._all: list[MineableSummary] | None = None

    async def _load_all(self) -> list[MineableSummary]:
        if self._all is not None:
            return self._all
        results: list[MineableSummary] = []
        for page_num in range(1, 10):
            payload = await self._client.get(
                _ENDPOINT,
                params={"page[size]": _PAGE_SIZE, "page[number]": page_num},
            )
            items = payload.get("data", [])
            for item in items:
                if (
                    item.get("has_ship_mineables")
                    or item.get("has_ground_vehicle_mineables")
                    or item.get("has_fps_mineables")
                ):
                    results.append(MineableSummary.from_api(item))
            meta = payload.get("meta", {})
            if page_num >= (meta.get("last_page") or 1):
                break
        self._all = results
        return results

    async def search(self, query: str) -> list[MineableSummary]:
        all_items = await self._load_all()
        if not query:
            return all_items
        q = query.lower()
        return [item for item in all_items if q in item.name.lower()]

    async def get(self, slug: str) -> Mineable:
        payload = await self._client.get(f"{_ENDPOINT}/{slug}")
        data = extract_data(payload)
        if not data:
            raise NotFoundError(f"No mineable found for {slug!r}")
        return Mineable.from_api(data)
