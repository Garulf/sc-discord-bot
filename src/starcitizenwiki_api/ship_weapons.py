"""Ship weapon component lookups on top of :class:`StarCitizenWikiClient`.

Ship weapons are exposed under ``/vehicle-weapons``. Supports:

* fetching one weapon by name or slug (``/vehicle-weapons/{name}``),
* a name-prefix search for autocomplete (``/vehicle-weapons?filter[name]=``),
* a parsed :class:`ShipWeapon` model with the stats worth displaying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api._common import (
    DEFAULT_LOCALE,
    PurchaseLocation,
    WikiResource,
    first_image,
    localize,
)


@dataclass(frozen=True)
class ShipWeapon:
    """A trimmed-down view of a ship-mounted weapon component."""

    uuid: str | None
    name: str
    slug: str | None
    manufacturer: str | None
    manufacturer_code: str | None
    description: str | None
    size: int | None
    grade: str | None
    classification: str | None
    type: str | None
    sub_type: str | None
    alpha_damage: float | None
    dps: float | None
    fire_rate: float | None
    range: float | None
    speed: float | None
    web_url: str | None
    image_url: str | None
    purchase_locations: list[PurchaseLocation] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> ShipWeapon:
        manufacturer = data.get("manufacturer") or {}
        weapon = data.get("weapon") or {}
        damage = weapon.get("damage") or {}
        uex = data.get("uex_prices") or {}
        purchases = [PurchaseLocation.from_api(p) for p in (uex.get("purchase") or []) if isinstance(p, dict)]

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
            image_url=first_image(data.get("images")),
            purchase_locations=purchases,
        )


class ShipWeapons(WikiResource[ShipWeapon]):
    """Ship weapon component endpoints bound to a :class:`StarCitizenWikiClient`."""

    endpoint = "vehicle-weapons"
    model = ShipWeapon
    noun = "ship weapon"
