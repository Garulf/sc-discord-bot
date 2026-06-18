"""Ship / vehicle lookups on top of :class:`StarCitizenWikiClient`.

The API exposes ships under ``/vehicles``. We support three things the bot
cares about:

* fetching one vehicle by name or slug (``/vehicles/{name}``),
* a name-prefix search for autocomplete (``/vehicles?filter[name]=``),
* a parsed :class:`Vehicle` model with just the fields worth showing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient

DEFAULT_LOCALE = "en_EN"


def localize(value: Any, locale: str = DEFAULT_LOCALE) -> Optional[str]:
    """Flatten the API's ``{locale: text}`` fields down to a single string.

    Many fields come back either as a plain string or as a dict keyed by locale
    (``en_EN``, ``de_DE``, ...). This returns the requested locale, falling back
    to English and then to any available translation.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in (locale, DEFAULT_LOCALE):
            text = value.get(key)
            if text:
                return text
        for text in value.values():
            if text:
                return text
    return None


@dataclass(frozen=True)
class Vehicle:
    """A trimmed-down view of a vehicle, parsed from the raw API payload."""

    uuid: Optional[str]
    name: str
    slug: Optional[str]
    manufacturer: Optional[str]
    manufacturer_code: Optional[str]
    description: Optional[str]
    type: Optional[str]
    production_status: Optional[str]
    career: Optional[str]
    role: Optional[str]
    size: Optional[str]
    size_class: Optional[int]
    foci: list[str]
    crew_min: Optional[int]
    crew_max: Optional[int]
    cargo_capacity: Optional[float]
    scm_speed: Optional[float]
    max_speed: Optional[float]
    health: Optional[float]
    shield_hp: Optional[float]
    armor_physical: Optional[float]
    armor_energy: Optional[float]
    deflection_physical: Optional[float]
    deflection_energy: Optional[float]
    signal_ir: Optional[float]
    signal_em: Optional[float]
    signal_cs: Optional[float]
    length: Optional[float]
    width: Optional[float]
    height: Optional[float]
    mass: Optional[float]
    msrp: Optional[float]
    pledge_url: Optional[str]
    web_url: Optional[str]
    image_url: Optional[str]

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> "Vehicle":
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
            image_url=_first_image(data.get("images")),
        )


def _first_image(images: Any) -> Optional[str]:
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if not isinstance(first, dict):
        return None
    return first.get("thumbnail_url") or first.get("original_url")


def _unique_by_slug(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate entries (the API lists each vehicle once per version)."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = item.get("slug") or item.get("name") or item.get("uuid") or ""
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


class Ships:
    """Vehicle endpoints bound to a :class:`StarCitizenWikiClient`."""

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, name_or_slug: str) -> Vehicle:
        """Fetch a single vehicle by exact name or slug.

        Raises :class:`NotFoundError` if no such vehicle exists.
        """
        payload = await self._client.get(f"vehicles/{name_or_slug.strip()}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            raise NotFoundError(f"No vehicle found for {name_or_slug!r}")
        return Vehicle.from_api(data, self._locale)

    async def search(self, query: str, *, limit: int = 25) -> list[Vehicle]:
        """Find vehicles whose name contains ``query`` (case-insensitive).

        Results are de-duplicated and capped at ``limit``. An empty/blank query
        returns an empty list rather than the entire catalogue.
        """
        query = query.strip()
        if not query:
            return []
        payload = await self._client.get(
            "vehicles",
            params={"filter[name]": query, "page[size]": min(limit * 2, 200)},
        )
        raw = payload.get("data", []) if isinstance(payload, dict) else []
        vehicles = _unique_by_slug(raw)[:limit]
        return [Vehicle.from_api(item, self._locale) for item in vehicles]

    async def browse(self, *, limit: int = 25) -> list[Vehicle]:
        """A sample of vehicles with no search filter, sorted by name.

        Used to populate autocomplete before the user types anything.
        """
        payload = await self._client.get(
            "vehicles", params={"page[size]": min(limit * 2, 200)}
        )
        raw = payload.get("data", []) if isinstance(payload, dict) else []
        vehicles = [Vehicle.from_api(item, self._locale) for item in _unique_by_slug(raw)]
        vehicles.sort(key=lambda vehicle: vehicle.name)
        return vehicles[:limit]

    async def find(self, query: str) -> Optional[Vehicle]:
        """Best-effort single match: prefer an exact name, else the first hit."""
        results = await self.search(query, limit=25)
        if not results:
            return None
        lowered = query.strip().lower()
        for vehicle in results:
            if vehicle.name.lower() == lowered:
                return vehicle
        return results[0]
