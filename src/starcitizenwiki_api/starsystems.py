from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, localize

_BASE = "https://api.star-citizen.wiki/api/starsystems"


@dataclass(frozen=True)
class StarSystem:
    uuid: str | None
    name: str
    slug: str | None
    code: str | None
    status: str | None
    type: str | None
    affiliation: str | None
    frost_line: float | None
    habitable_zone_inner: float | None
    habitable_zone_outer: float | None
    description: str | None
    web_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> StarSystem:
        affiliation_raw = data.get("affiliation")
        if isinstance(affiliation_raw, list):
            affiliation = ", ".join(a["name"] for a in affiliation_raw if isinstance(a, dict) and a.get("name"))
        else:
            affiliation = localize(affiliation_raw, locale)
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("code") or data.get("slug"),
            code=data.get("code"),
            status=data.get("status"),
            type=data.get("type"),
            affiliation=affiliation or None,
            frost_line=data.get("frost_line"),
            habitable_zone_inner=data.get("habitable_zone_inner"),
            habitable_zone_outer=data.get("habitable_zone_outer"),
            description=localize(data.get("description"), locale),
            web_url=data.get("web_url"),
        )


class StarSystems(WikiResource[StarSystem]):
    endpoint = _BASE
    model = StarSystem
    noun = "star system"
