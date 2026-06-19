from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, localize

_BASE = "https://api.star-citizen.wiki/api/celestial-objects"


@dataclass(frozen=True)
class CelestialObject:
    uuid: str | None
    name: str
    slug: str | None
    code: str | None
    designation: str | None
    type: str | None
    sub_type: str | None
    parent_name: str | None
    star_system_name: str | None
    habitable: bool | None
    age: float | None
    distance: float | None
    orbit_period: float | None
    description: str | None
    web_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> CelestialObject:
        sub_type = data.get("sub_type") or {}
        parent = data.get("parent") or {}
        star = data.get("star") or {}
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("code") or data.get("slug"),
            code=data.get("code"),
            designation=data.get("designation"),
            type=data.get("type"),
            sub_type=sub_type.get("name") if isinstance(sub_type, dict) else localize(sub_type, locale),
            parent_name=parent.get("name") if isinstance(parent, dict) else None,
            star_system_name=star.get("name") if isinstance(star, dict) else data.get("system"),
            habitable=data.get("habitable"),
            age=data.get("age"),
            distance=data.get("distance"),
            orbit_period=data.get("orbit_period"),
            description=localize(data.get("description"), locale),
            web_url=data.get("web_url"),
        )


class CelestialObjects(WikiResource[CelestialObject]):
    endpoint = _BASE
    model = CelestialObject
    noun = "celestial object"
