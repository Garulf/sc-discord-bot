from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, localize

_BASE = "https://api.star-citizen.wiki/api/factions"


@dataclass(frozen=True)
class Faction:
    uuid: str | None
    name: str
    slug: str | None
    faction_type: str | None
    lawful: bool | None
    has_reputation: bool | None
    headquarters: str | None
    area: str | None
    focus: str | None
    founded: str | None
    leadership: str | None
    description: str | None
    web_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Faction:
        leadership_raw = data.get("leadership")
        if isinstance(leadership_raw, list):
            leadership = ", ".join(str(x) for x in leadership_raw if x)
        else:
            leadership = leadership_raw
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("uuid"),
            faction_type=data.get("faction_type"),
            lawful=data.get("lawful"),
            has_reputation=data.get("has_reputation"),
            headquarters=data.get("headquarters"),
            area=data.get("area"),
            focus=data.get("focus"),
            founded=str(data.get("founded")) if data.get("founded") else None,
            leadership=leadership,
            description=localize(data.get("description"), locale),
            web_url=data.get("web_url"),
        )


class Factions(WikiResource[Faction]):
    endpoint = _BASE
    model = Faction
    noun = "faction"
