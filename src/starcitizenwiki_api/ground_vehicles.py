from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, first_image, localize

_BASE = "https://api.star-citizen.wiki/api/ground-vehicles"


@dataclass(frozen=True)
class GroundVehicle:
    uuid: str | None
    name: str
    slug: str | None
    manufacturer: str | None
    manufacturer_code: str | None
    description: str | None
    career: str | None
    role: str | None
    crew_min: int | None
    crew_max: int | None
    max_speed: float | None
    length: float | None
    width: float | None
    height: float | None
    mass: float | None
    msrp: float | None
    web_url: str | None
    image_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> GroundVehicle:
        manufacturer = data.get("manufacturer") or {}
        crew = data.get("crew") or {}
        speed = data.get("speed") or {}
        dim = data.get("dimension") or data.get("sizes") or {}
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("slug"),
            manufacturer=manufacturer.get("name") if isinstance(manufacturer, dict) else localize(manufacturer, locale),
            manufacturer_code=manufacturer.get("code") if isinstance(manufacturer, dict) else None,
            description=localize(data.get("game_description") or data.get("description"), locale),
            career=localize(data.get("career"), locale),
            role=localize(data.get("role"), locale),
            crew_min=crew.get("min") if isinstance(crew, dict) else None,
            crew_max=crew.get("max") if isinstance(crew, dict) else None,
            max_speed=speed.get("max") if isinstance(speed, dict) else None,
            length=dim.get("length") if isinstance(dim, dict) else None,
            width=dim.get("width") or dim.get("beam") if isinstance(dim, dict) else None,
            height=dim.get("height") if isinstance(dim, dict) else None,
            mass=data.get("mass_total") or data.get("mass"),
            msrp=data.get("msrp"),
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
        )


class GroundVehicles(WikiResource[GroundVehicle]):
    endpoint = _BASE
    model = GroundVehicle
    noun = "ground vehicle"
