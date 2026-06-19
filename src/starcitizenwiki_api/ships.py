"""Ship / vehicle lookups on top of :class:`StarCitizenWikiClient`.

The API exposes ships under ``/vehicles``. We support three things the bot
cares about:

* fetching one vehicle by name or slug (``/vehicles/{name}``),
* a name-prefix search for autocomplete (``/vehicles?filter[name]=``),
* a parsed :class:`Vehicle` model with just the fields worth showing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import (
    DEFAULT_LOCALE,
    DEFAULT_SEARCH_LIMIT,
    MAX_PAGE_SIZE,
    SEARCH_OVERFETCH_FACTOR,
    WikiResource,
    extract_data,
    first_image,
    localize,
    unique_by_slug,
)

__all__ = ["DEFAULT_LOCALE", "Ships", "Vehicle", "localize"]


@dataclass(frozen=True)
class Vehicle:
    """A trimmed-down view of a vehicle, parsed from the raw API payload."""

    uuid: str | None
    name: str
    slug: str | None
    manufacturer: str | None
    manufacturer_code: str | None
    description: str | None
    type: str | None
    production_status: str | None
    career: str | None
    role: str | None
    size: str | None
    size_class: int | None
    foci: list[str]
    crew_min: int | None
    crew_max: int | None
    cargo_capacity: float | None
    scm_speed: float | None
    max_speed: float | None
    health: float | None
    shield_hp: float | None
    armor_physical: float | None
    armor_energy: float | None
    deflection_physical: float | None
    deflection_energy: float | None
    signal_ir: float | None
    signal_em: float | None
    signal_cs: float | None
    length: float | None
    width: float | None
    height: float | None
    mass: float | None
    msrp: float | None
    pledge_url: str | None
    web_url: str | None
    image_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Vehicle:
        manufacturer = data.get("manufacturer") or {}
        crew = data.get("crew") or {}
        speed = data.get("speed") or {}
        armor = data.get("armor") or {}
        dimension = data.get("dimension") or data.get("sizes") or {}
        foci = [text for f in (data.get("foci") or []) if (text := localize(f, locale))]

        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or data.get("game_name") or "Unknown",
            slug=data.get("slug"),
            manufacturer=manufacturer.get("name"),
            manufacturer_code=manufacturer.get("code"),
            description=localize(data.get("description"), locale),
            type=localize(data.get("type"), locale),
            production_status=localize(data.get("production_status"), locale),
            career=data.get("career"),
            role=data.get("role"),
            size=localize(data.get("size"), locale),
            size_class=data.get("size_class"),
            foci=foci,
            crew_min=crew.get("min"),
            crew_max=crew.get("max"),
            cargo_capacity=data.get("cargo_capacity"),
            scm_speed=speed.get("scm"),
            max_speed=speed.get("max"),
            health=data.get("health"),
            shield_hp=data.get("shield_hp"),
            armor_physical=armor.get("damage_physical"),
            armor_energy=armor.get("damage_energy"),
            deflection_physical=(armor.get("deflection") or {}).get("physical"),
            deflection_energy=(armor.get("deflection") or {}).get("energy"),
            signal_ir=armor.get("signal_infrared"),
            signal_em=armor.get("signal_electromagnetic"),
            signal_cs=armor.get("signal_cross_section"),
            length=dimension.get("length"),
            width=dimension.get("width") or dimension.get("beam"),
            height=dimension.get("height"),
            mass=data.get("mass"),
            msrp=data.get("msrp"),
            pledge_url=data.get("pledge_url"),
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
        )


class Ships(WikiResource[Vehicle]):
    """Vehicle endpoints bound to a :class:`StarCitizenWikiClient`."""

    endpoint = "vehicles"
    model = Vehicle
    noun = "vehicle"

    async def browse(self, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[Vehicle]:
        """A sample of vehicles with no search filter, sorted by name.

        Used to populate autocomplete before the user types anything.
        """
        payload = await self._client.get(
            self.endpoint, params={"page[size]": min(limit * SEARCH_OVERFETCH_FACTOR, MAX_PAGE_SIZE)}
        )
        raw = extract_data(payload, [])
        vehicles = [Vehicle.from_api(item, self._locale) for item in unique_by_slug(raw)]
        vehicles.sort(key=lambda vehicle: vehicle.name)
        return vehicles[:limit]

    async def find(self, query: str) -> Vehicle | None:
        """Best-effort single match: prefer an exact name, else the first hit.

        Unlike most resources, the vehicle payload from search already carries
        everything the bot shows, so there's no need to re-fetch by slug.
        """
        results = await self.search(query, limit=DEFAULT_SEARCH_LIMIT)
        if not results:
            return None
        return self._pick_best(results, query)
