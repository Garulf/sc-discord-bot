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
class Item:
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
    web_url: str | None
    image_url: str | None
    purchase_locations: list[PurchaseLocation] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Item:
        manufacturer = data.get("manufacturer") or {}
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
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
            purchase_locations=purchases,
        )


class Items(WikiResource[Item]):
    endpoint = "items"
    model = Item
    noun = "item"
