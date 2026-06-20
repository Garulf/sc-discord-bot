from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, WikiResource, first_image, localized

_BASE = "https://api.star-citizen.wiki/api/manufacturers"


@dataclass(frozen=True)
class Manufacturer:
    uuid: str | None
    name: str
    slug: str | None
    code: str | None
    description: str | None
    known_for: str | None
    web_url: str | None
    image_url: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Manufacturer:
        return cls(
            uuid=data.get("uuid"),
            name=data.get("name") or "Unknown",
            slug=data.get("code") or data.get("slug"),
            code=data.get("code"),
            description=localized(data, "description", locale),
            known_for=localized(data, "known_for", locale),
            web_url=data.get("web_url"),
            image_url=first_image(data.get("images")),
        )


class Manufacturers(WikiResource[Manufacturer]):
    endpoint = _BASE
    model = Manufacturer
    noun = "manufacturer"
