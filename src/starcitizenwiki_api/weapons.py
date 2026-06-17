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
from typing import Any, Optional

from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient
from src.starcitizenwiki_api.ships import DEFAULT_LOCALE, localize


@dataclass(frozen=True)
class PurchaseLocation:
    """A single in-game shop terminal that stocks a weapon, from UEX data."""

    price_buy: Optional[float]
    terminal_name: Optional[str]
    location_name: Optional[str]
    star_system: Optional[str]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "PurchaseLocation":
        location = data.get("starmap_location") or {}
        return cls(
            price_buy=data.get("price_buy"),
            terminal_name=data.get("terminal_name"),
            location_name=location.get("name"),
            star_system=location.get("star_system_name"),
        )


@dataclass(frozen=True)
class Weapon:
    """A trimmed-down view of a personal weapon, parsed from the raw API payload."""

    uuid: Optional[str]
    name: str
    slug: Optional[str]
    manufacturer: Optional[str]
    manufacturer_code: Optional[str]
    description: Optional[str]
    classification: Optional[str]
    weapon_type: Optional[str]
    size: Optional[int]
    fire_mode: Optional[str]
    magazine_size: Optional[int]
    rpm: Optional[float]
    effective_range: Optional[float]
    damage_per_shot: Optional[float]
    alpha_damage: Optional[float]
    dps: Optional[float]
    ammunition_type: Optional[str]
    web_url: Optional[str]
    image_url: Optional[str]
    purchase_locations: list[PurchaseLocation] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> "Weapon":
        manufacturer = data.get("manufacturer") or {}
        weapon = data.get("personal_weapon") or {}
        damage = weapon.get("damage") or {}
        ammunition = weapon.get("ammunition") or {}
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


def _is_base_model(weapon: Weapon) -> bool:
    """Whether a weapon is a base model rather than a cosmetic skin variant.

    Skins are named with a quoted nickname (e.g. ``A03 "Canuto" Sniper Rifle``);
    the base model has a plain name (``A03 Sniper Rifle``). Only the base model
    carries shop/price data, so callers favour it when picking buy locations.
    """
    return '"' not in weapon.name


def _unique_by_slug(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate entries (the API lists each weapon once per version)."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = item.get("slug") or item.get("name") or item.get("uuid") or ""
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


class Weapons:
    """Personal-weapon endpoints bound to a :class:`StarCitizenWikiClient`."""

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, name_or_slug: str) -> Weapon:
        """Fetch a single weapon by exact name or slug.

        Raises :class:`NotFoundError` if no such weapon exists.
        """
        payload = await self._client.get(f"weapons/{name_or_slug.strip()}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            raise NotFoundError(f"No weapon found for {name_or_slug!r}")
        return Weapon.from_api(data, self._locale)

    async def search(self, query: str, *, limit: int = 25) -> list[Weapon]:
        """Find weapons whose name contains ``query`` (case-insensitive).

        Results are de-duplicated and capped at ``limit``. An empty/blank query
        returns an empty list rather than the entire catalogue.
        """
        query = query.strip()
        if not query:
            return []
        payload = await self._client.get(
            "weapons",
            params={"filter[name]": query, "page[size]": min(limit * 2, 200)},
        )
        raw = payload.get("data", []) if isinstance(payload, dict) else []
        weapons = _unique_by_slug(raw)[:limit]
        return [Weapon.from_api(item, self._locale) for item in weapons]

    async def find(self, query: str) -> Optional[Weapon]:
        """Best-effort single match for a search query.

        Preference order: an exact name match, then the base model over its
        skins, then the first hit. Skins are named with a quoted nickname (e.g.
        ``A03 "Canuto" Sniper Rifle``) and carry no shop data — buy locations
        live on the plain base model (``A03 Sniper Rifle``), so we favour it.

        The search endpoint omits the per-item ``uex_prices`` shop data, so the
        chosen weapon is re-fetched by slug to pull in its buy locations.
        """
        results = await self.search(query, limit=25)
        if not results:
            return None
        match = self._pick_best(results, query)
        if match.slug:
            try:
                return await self.get(match.slug)
            except NotFoundError:
                return match
        return match

    @staticmethod
    def _pick_best(results: list[Weapon], query: str) -> Weapon:
        """Choose the most relevant weapon from search results.

        Prefer an exact name match, then a base model over its skins, then fall
        back to the first result.
        """
        lowered = query.strip().lower()

        for weapon in results:
            if weapon.name.lower() == lowered:
                return weapon

        for weapon in results:
            if _is_base_model(weapon):
                return weapon

        return results[0]
