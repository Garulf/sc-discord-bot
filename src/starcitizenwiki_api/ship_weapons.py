"""Ship weapon component lookups on top of :class:`StarCitizenWikiClient`.

Ship weapons are exposed under ``/vehicle-weapons``. Supports:

* fetching one weapon by name or slug (``/vehicle-weapons/{name}``),
* a name-prefix search for autocomplete (``/vehicle-weapons?filter[name]=``),
* a parsed :class:`ShipWeapon` model with the stats worth displaying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient
from src.starcitizenwiki_api.ships import DEFAULT_LOCALE, localize
from src.starcitizenwiki_api.weapons import PurchaseLocation


@dataclass(frozen=True)
class ShipWeapon:
    """A trimmed-down view of a ship-mounted weapon component."""

    uuid: Optional[str]
    name: str
    slug: Optional[str]
    manufacturer: Optional[str]
    manufacturer_code: Optional[str]
    description: Optional[str]
    size: Optional[int]
    grade: Optional[str]
    classification: Optional[str]
    type: Optional[str]
    sub_type: Optional[str]
    alpha_damage: Optional[float]
    dps: Optional[float]
    fire_rate: Optional[float]
    range: Optional[float]
    speed: Optional[float]
    web_url: Optional[str]
    image_url: Optional[str]
    purchase_locations: list[PurchaseLocation] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> "ShipWeapon":
        manufacturer = data.get("manufacturer") or {}
        weapon = data.get("weapon") or {}
        damage = weapon.get("damage") or {}
        uex = data.get("uex_prices") or {}
        purchases = [
            PurchaseLocation.from_api(p)
            for p in (uex.get("purchase") or [])
            if isinstance(p, dict)
        ]

        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("slug"),
            manufacturer=manufacturer.get("name"),
            manufacturer_code=manufacturer.get("code"),
            description=localize(data.get("description"), locale),
            size=data.get("size"),
            grade=data.get("grade"),
            classification=data.get("class") or data.get("classification"),
            type=localize(data.get("type"), locale),
            sub_type=localize(data.get("sub_type"), locale),
            alpha_damage=damage.get("alpha_damage") or damage.get("alpha_total"),
            dps=damage.get("dps_total") or damage.get("dps"),
            fire_rate=weapon.get("fire_rate") or weapon.get("rpm"),
            range=weapon.get("range"),
            speed=weapon.get("speed"),
            web_url=data.get("web_url"),
            image_url=_first_image(data.get("images")),
            purchase_locations=purchases,
        )


def _first_image(images: Any) -> Optional[str]:
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if not isinstance(first, dict):
        return None
    return first.get("thumbnail_url") or first.get("original_url")


def _unique_by_slug(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = item.get("slug") or item.get("name") or item.get("uuid") or ""
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


class ShipWeapons:
    """Ship weapon component endpoints bound to a :class:`StarCitizenWikiClient`."""

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, name_or_slug: str) -> ShipWeapon:
        """Fetch a single ship weapon by exact name or slug.

        Raises :class:`NotFoundError` if no match exists.
        """
        payload = await self._client.get(f"vehicle-weapons/{name_or_slug.strip()}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            raise NotFoundError(f"No ship weapon found for {name_or_slug!r}")
        return ShipWeapon.from_api(data, self._locale)

    async def search(self, query: str, *, limit: int = 25) -> list[ShipWeapon]:
        """Find ship weapons whose name contains ``query`` (case-insensitive)."""
        query = query.strip()
        if not query:
            return []
        payload = await self._client.get(
            "vehicle-weapons",
            params={"filter[name]": query, "page[size]": min(limit * 2, 200)},
        )
        raw = payload.get("data", []) if isinstance(payload, dict) else []
        items = _unique_by_slug(raw)[:limit]
        return [ShipWeapon.from_api(item, self._locale) for item in items]

    async def find(self, query: str) -> Optional[ShipWeapon]:
        """Best-effort single match: prefer exact name, then first hit.

        Re-fetches the chosen entry by slug to pull in full stats.
        """
        results = await self.search(query, limit=25)
        if not results:
            return None
        lowered = query.strip().lower()
        match = next((w for w in results if w.name.lower() == lowered), results[0])
        if match.slug:
            try:
                return await self.get(match.slug)
            except NotFoundError:
                return match
        return match
