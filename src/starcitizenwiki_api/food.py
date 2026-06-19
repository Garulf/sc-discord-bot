from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, first_image, localize

_BASE = "https://api.star-citizen.wiki/api/food"


@dataclass(frozen=True)
class FoodItem:
    uuid: str | None
    name: str
    slug: str | None
    manufacturer: str | None
    description: str | None
    type: str | None
    classification_label: str | None
    size: int | None
    mass: float | None
    event_source: list[str] = field(default_factory=list)
    web_url: str | None = None
    image_url: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> FoodItem:
        manufacturer = data.get("manufacturer") or {}
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("slug"),
            manufacturer=manufacturer.get("name") if isinstance(manufacturer, dict) else localize(manufacturer, locale),
            description=localize(data.get("description"), locale),
            type=data.get("type_label") or data.get("type"),
            classification_label=data.get("classification_label"),
            size=data.get("size"),
            mass=data.get("mass"),
            event_source=[e for e in (data.get("event_source") or []) if isinstance(e, str)],
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
        )


class Food(WikiResource[FoodItem]):
    endpoint = _BASE
    model = FoodItem
    noun = "food item"
