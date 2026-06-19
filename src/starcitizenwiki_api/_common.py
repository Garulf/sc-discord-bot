"""Shared building blocks for the star-citizen.wiki resource modules.

Every resource (ships, weapons, armor, ...) parses the same payload shapes and
talks to the API the same way. This module holds the pieces they all reuse so
each resource file only has to declare what makes it different: its endpoint,
its parsed model, and the noun for its error messages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient

DEFAULT_LOCALE = "en_EN"

# The search endpoint omits per-item shop data and lists near-duplicates, so we
# over-fetch and de-duplicate before trimming back to the caller's limit.
SEARCH_OVERFETCH_FACTOR = 2
MAX_PAGE_SIZE = 200
DEFAULT_SEARCH_LIMIT = 25


def localize(value: Any, locale: str = DEFAULT_LOCALE) -> str | None:
    """Flatten the API's ``{locale: text}`` fields down to a single string.

    Many fields come back either as a plain string or as a dict keyed by locale
    (``en_EN``, ``de_DE``, ...). This returns the requested locale, falling back
    to English and then to any available translation.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in (locale, DEFAULT_LOCALE):
            text = value.get(key)
            if text:
                return text
        for text in value.values():
            if text:
                return text
    return None


def first_image(images: Any) -> str | None:
    """Return the best thumbnail URL from an API ``images`` list, if any."""
    if not isinstance(images, list) or not images:
        return None
    first = images[0]
    if not isinstance(first, dict):
        return None
    return first.get("thumbnail_url") or first.get("original_url")


def unique_by_slug(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate entries (the API lists each item once per version)."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = item.get("slug") or item.get("name") or item.get("uuid") or ""
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def extract_data(payload: Any, default: Any = None) -> Any:
    """Pull the ``data`` envelope out of an API payload, tolerating odd shapes."""
    return payload.get("data", default) if isinstance(payload, dict) else default


@dataclass(frozen=True)
class PurchaseLocation:
    """A single in-game shop terminal that stocks an item, from UEX data."""

    price_buy: float | None
    terminal_name: str | None
    location_name: str | None
    star_system: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> PurchaseLocation:
        location = data.get("starmap_location") or {}
        return cls(
            price_buy=data.get("price_buy"),
            terminal_name=data.get("terminal_name"),
            location_name=location.get("name"),
            star_system=location.get("star_system_name"),
        )


ModelT = TypeVar("ModelT")


class WikiResource(Generic[ModelT]):
    """Base for a catalogue endpoint: ``get`` one, ``search`` many, ``find`` best.

    Subclasses set three class attributes — ``endpoint`` (the API path),
    ``model`` (the dataclass with a ``from_api`` parser), and ``noun`` (used in
    not-found messages). They may override :meth:`_pick_best` to change how a
    single result is chosen from a search.
    """

    endpoint: str
    model: type[ModelT]
    noun: str

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, name_or_slug: str) -> ModelT:
        """Fetch a single record by exact name or slug.

        Raises :class:`NotFoundError` if no such record exists.
        """
        payload = await self._client.get(f"{self.endpoint}/{name_or_slug.strip()}")
        data = extract_data(payload)
        if not data:
            raise NotFoundError(f"No {self.noun} found for {name_or_slug!r}")
        return self.model.from_api(data, self._locale)

    async def search(self, query: str, *, limit: int = DEFAULT_SEARCH_LIMIT) -> list[ModelT]:
        """Find records whose name contains ``query`` (case-insensitive).

        Results are de-duplicated and capped at ``limit``. An empty/blank query
        returns an empty list rather than the entire catalogue.
        """
        query = query.strip()
        params: dict[str, Any] = {"page[size]": min(limit * SEARCH_OVERFETCH_FACTOR, MAX_PAGE_SIZE)}
        if query:
            params["filter[name]"] = query
        payload = await self._client.get(self.endpoint, params=params)
        raw = extract_data(payload, [])
        items = unique_by_slug(raw)[:limit]
        return [self.model.from_api(item, self._locale) for item in items]

    async def find(self, query: str) -> ModelT | None:
        """Best-effort single match for a search query.

        Picks the most relevant search hit (see :meth:`_pick_best`) and re-fetches
        it by slug so the result carries the full per-item shop/price data that
        the search endpoint omits.
        """
        results = await self.search(query, limit=DEFAULT_SEARCH_LIMIT)
        if not results:
            return None
        match = self._pick_best(results, query)
        if match.slug:
            try:
                return await self.get(match.slug)
            except NotFoundError:
                return match
        return match

    def _pick_best(self, results: list[ModelT], query: str) -> ModelT:
        """Choose the most relevant result: an exact name match, else the first."""
        lowered = query.strip().lower()
        return next((item for item in results if item.name.lower() == lowered), results[0])
