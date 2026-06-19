from __future__ import annotations

from dataclasses import dataclass, field
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

_BASE = "https://api.star-citizen.wiki/api/galactapedia"


@dataclass(frozen=True)
class GalactapediaArticle:
    id: str | None
    title: str
    slug: str | None
    excerpt: str | None
    content: str | None
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    web_url: str | None = None

    @property
    def name(self) -> str:
        return self.title

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> GalactapediaArticle:
        translations = data.get("translations") or {}
        content = localize(translations, locale)
        return cls(
            id=data.get("id"),
            title=data.get("title") or "Unknown",
            slug=data.get("slug") or data.get("id"),
            excerpt=data.get("excerpt"),
            content=content,
            categories=[c["name"] for c in (data.get("categories") or []) if isinstance(c, dict) and c.get("name")],
            tags=[t["name"] for t in (data.get("tags") or []) if isinstance(t, dict) and t.get("name")],
            web_url=data.get("web_url"),
        )


class Galactapedia(WikiResource[GalactapediaArticle]):
    endpoint = _BASE
    model = GalactapediaArticle
    noun = "galactapedia article"

    async def search(self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[GalactapediaArticle]:
        params: dict[str, Any] = {"page[size]": min(limit * SEARCH_OVERFETCH_FACTOR, MAX_PAGE_SIZE)}
        if query.strip():
            params["filter[query]"] = query.strip()
        payload = await self._client.get(self.endpoint, params=params)
        raw = extract_data(payload, [])
        items = unique_by_slug(raw)[:limit]
        return [self.model.from_api(item, self._locale) for item in items]
