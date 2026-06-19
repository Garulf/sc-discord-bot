from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, first_image, localize

_BASE = "https://api.star-citizen.wiki/api/locations"


@dataclass(frozen=True)
class Location:
    uuid: str | None
    name: str
    slug: str | None
    type: str | None
    type_name: str | None
    star_system_name: str | None
    parent_name: str | None
    designation: str | None
    description: str | None
    web_url: str | None
    image_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Location:
        type_obj = data.get("type") or {}
        parent = data.get("parent") or {}
        star = data.get("star") or {}
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("slug"),
            type=type_obj.get("classification") if isinstance(type_obj, dict) else localize(type_obj, locale),
            type_name=type_obj.get("name") if isinstance(type_obj, dict) else None,
            star_system_name=star.get("name") if isinstance(star, dict) else data.get("system"),
            parent_name=parent.get("name") if isinstance(parent, dict) else None,
            designation=data.get("designation"),
            description=localize(data.get("description"), locale),
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
        )


class Locations(WikiResource[Location]):
    endpoint = _BASE
    model = Location
    noun = "location"
