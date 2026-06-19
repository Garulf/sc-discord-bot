from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient
from src.starcitizenwiki_api.ships import DEFAULT_LOCALE, localize
from src.starcitizenwiki_api.weapons import PurchaseLocation


@dataclass(frozen=True)
class ArmorItem:
    uuid: str | None
    name: str
    slug: str | None
    manufacturer: str | None
    manufacturer_code: str | None
    description: str | None
    type: str | None
    sub_type: str | None
    size: int | None
    grade: str | None
    classification: str | None
    damage_reduction: float | None
    capacity: float | None
    web_url: str | None
    image_url: str | None
    purchase_locations: list[PurchaseLocation] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> ArmorItem:
        manufacturer = data.get("manufacturer") or {}
        armor = data.get("armor") or {}
        uex = data.get("uex_prices") or {}
        purchases = [PurchaseLocation.from_api(p) for p in (uex.get("purchase") or []) if isinstance(p, dict)]
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("slug"),
            manufacturer=manufacturer.get("name"),
            manufacturer_code=manufacturer.get("code"),
            description=localize(data.get("description"), locale),
            type=localize(data.get("type"), locale),
            sub_type=localize(data.get("sub_type"), locale),
            size=data.get("size"),
            grade=data.get("grade"),
            classification=data.get("class"),
            damage_reduction=armor.get("damage_reduction"),
            capacity=armor.get("capacity"),
            web_url=data.get("web_url"),
            image_url=_first_image(data.get("images")),
            purchase_locations=purchases,
        )


def _first_image(images: Any) -> str | None:
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


class Armor:
    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, name_or_slug: str) -> ArmorItem:
        payload = await self._client.get(f"armor/{name_or_slug.strip()}")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not data:
            raise NotFoundError(f"No armor found for {name_or_slug!r}")
        return ArmorItem.from_api(data, self._locale)

    async def search(self, query: str, *, limit: int = 25) -> list[ArmorItem]:
        query = query.strip()
        if not query:
            return []
        payload = await self._client.get(
            "armor",
            params={"filter[name]": query, "page[size]": min(limit * 2, 200)},
        )
        raw = payload.get("data", []) if isinstance(payload, dict) else []
        items = _unique_by_slug(raw)[:limit]
        return [ArmorItem.from_api(item, self._locale) for item in items]

    async def find(self, query: str) -> ArmorItem | None:
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
