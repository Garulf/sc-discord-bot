from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api._common import (
    DEFAULT_LOCALE,
    PurchaseLocation,
    WikiResource,
    first_image,
    localized,
    parse_manufacturer,
    parse_purchase_locations,
)


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
        armor = data.get("armor") or {}
        manufacturer, manufacturer_code = parse_manufacturer(data)
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("slug"),
            manufacturer=manufacturer,
            manufacturer_code=manufacturer_code,
            description=localized(data, "description", locale),
            type=localized(data, "type", locale),
            sub_type=localized(data, "sub_type", locale),
            size=data.get("size"),
            grade=data.get("grade"),
            classification=data.get("class"),
            damage_reduction=armor.get("damage_reduction"),
            capacity=armor.get("capacity"),
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
            purchase_locations=parse_purchase_locations(data),
        )


class Armor(WikiResource[ArmorItem]):
    endpoint = "armor"
    model = ArmorItem
    noun = "armor"
