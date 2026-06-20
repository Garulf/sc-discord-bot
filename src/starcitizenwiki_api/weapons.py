"""FPS / personal weapon lookups on top of :class:`StarCitizenWikiClient`.

The API exposes personal weapons under ``/weapons``. We support the same shape
as :mod:`src.starcitizenwiki_api.ships`:

* fetching one weapon by name or slug (``/weapons/{name}``),
* a name-prefix search for autocomplete (``/weapons?filter[name]=``),
* a parsed :class:`Weapon` model with the stats worth showing, including the
  in-game shops (``uex_prices.purchase``) where the weapon can be bought.
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
    localized,
    parse_manufacturer,
    parse_purchase_locations,
)


@dataclass(frozen=True)
class Weapon:
    """A trimmed-down view of a personal weapon, parsed from the raw API payload."""

    uuid: str | None
    name: str
    slug: str | None
    manufacturer: str | None
    manufacturer_code: str | None
    description: str | None
    classification: str | None
    weapon_type: str | None
    size: int | None
    fire_mode: str | None
    magazine_size: int | None
    rpm: float | None
    effective_range: float | None
    damage_per_shot: float | None
    alpha_damage: float | None
    dps: float | None
    ammunition_type: str | None
    web_url: str | None
    image_url: str | None
    purchase_locations: list[PurchaseLocation] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Weapon:
        weapon = data.get("personal_weapon") or {}
        damage = weapon.get("damage") or {}
        ammunition = weapon.get("ammunition") or {}
        manufacturer, manufacturer_code = parse_manufacturer(data)

        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("slug"),
            manufacturer=manufacturer,
            manufacturer_code=manufacturer_code,
            description=localized(data, "description", locale),
            classification=data.get("classification_label") or data.get("classification"),
            weapon_type=localize(weapon.get("type"), locale),
            size=data.get("size"),
            fire_mode=weapon.get("fire_mode"),
            magazine_size=weapon.get("magazine_size"),
            rpm=weapon.get("rpm") or weapon.get("rof"),
            effective_range=weapon.get("effective_range"),
            damage_per_shot=weapon.get("damage_per_shot"),
            alpha_damage=damage.get("alpha_total"),
            dps=damage.get("dps_total"),
            ammunition_type=localize(ammunition.get("type"), locale),
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
            purchase_locations=parse_purchase_locations(data),
        )


def _is_base_model(weapon: Weapon) -> bool:
    """Whether a weapon is a base model rather than a cosmetic skin variant.

    Skins are named with a quoted nickname (e.g. ``A03 "Canuto" Sniper Rifle``);
    the base model has a plain name (``A03 Sniper Rifle``). Only the base model
    carries shop/price data, so callers favour it when picking buy locations.
    """
    return '"' not in weapon.name


class Weapons(WikiResource[Weapon]):
    """Personal-weapon endpoints bound to a :class:`StarCitizenWikiClient`.

    ``find`` favours the base model over its cosmetic skins because only the base
    model carries shop/price data — skins are named with a quoted nickname (e.g.
    ``A03 "Canuto" Sniper Rifle``) while the base is plain (``A03 Sniper Rifle``).
    """

    endpoint = "weapons"
    model = Weapon
    noun = "weapon"

    def _pick_best(self, results: list[Weapon], query: str) -> Weapon:
        lowered = query.strip().lower()

        for weapon in results:
            if weapon.name.lower() == lowered:
                return weapon

        for weapon in results:
            if _is_base_model(weapon):
                return weapon

        return results[0]
