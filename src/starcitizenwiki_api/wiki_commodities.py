from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, first_image, localize

_BASE = "https://api.star-citizen.wiki/api/commodities"


@dataclass(frozen=True)
class WikiCommodity:
    uuid: str | None
    name: str
    slug: str | None
    description: str | None
    commodity_groups: list[str] = field(default_factory=list)
    is_mineable: bool | None = None
    is_harvestable: bool | None = None
    is_illegal: bool | None = None
    is_temporary: bool | None = None
    web_url: str | None = None
    image_url: str | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> WikiCommodity:
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or data.get("display_name") or "Unknown",
            slug=data.get("slug"),
            description=localize(data.get("description"), locale),
            commodity_groups=[g for g in (data.get("commodity_groups") or []) if isinstance(g, str)],
            is_mineable=data.get("is_mineable"),
            is_harvestable=data.get("has_harvestables") or data.get("is_harvestable"),
            is_illegal=data.get("is_illegal"),
            is_temporary=data.get("is_temporary"),
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
        )


class WikiCommodities(WikiResource[WikiCommodity]):
    endpoint = _BASE
    model = WikiCommodity
    noun = "commodity"
