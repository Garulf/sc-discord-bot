from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import (
    DEFAULT_LOCALE,
    DEFAULT_SEARCH_LIMIT,
    MAX_PAGE_SIZE,
    SEARCH_OVERFETCH_FACTOR,
    WikiResource,
    extract_data,
    localize,
    unique_by_slug,
)

_BASE = "https://api.star-citizen.wiki/api/comm-links"


@dataclass(frozen=True)
class CommLink:
    id: int | None
    title: str
    slug: str | None
    channel: str | None
    category: str | None
    series: str | None
    content: str | None
    rsi_url: str | None
    web_url: str | None
    published_at: str | None

    @property
    def name(self) -> str:
        return self.title

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> CommLink:
        translations = data.get("translations") or {}
        return cls(
            id=data.get("id"),
            title=data.get("title") or "Unknown",
            slug=str(data["id"]) if data.get("id") is not None else None,
            channel=data.get("channel"),
            category=data.get("category"),
            series=data.get("series"),
            content=localize(translations, locale),
            rsi_url=data.get("rsi_url"),
            web_url=data.get("api_public_url") or data.get("web_url"),
            published_at=data.get("created_at"),
        )


class CommLinks(WikiResource[CommLink]):
    endpoint = _BASE
    model = CommLink
    noun = "comm-link"

    async def search(self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[CommLink]:
        params: dict[str, Any] = {"page[size]": min(limit * SEARCH_OVERFETCH_FACTOR, MAX_PAGE_SIZE)}
        if query.strip():
            params["filter[title]"] = query.strip()
        payload = await self._client.get(self.endpoint, params=params)
        raw = extract_data(payload, [])
        items = unique_by_slug(raw)[:limit]
        return [self.model.from_api(item, self._locale) for item in items]
