from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, extract_data
from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient

_BASE = "https://api.star-citizen.wiki/api/game-versions"


@dataclass(frozen=True)
class GameVersion:
    code: str
    channel: str | None
    is_default: bool | None
    released_at: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> GameVersion:
        return cls(
            code=data.get("code") or "",
            channel=data.get("channel"),
            is_default=data.get("is_default"),
            released_at=data.get("released_at"),
        )


class GameVersions:
    """Game versions from the star-citizen.wiki API (``/api/game-versions``)."""

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, version: str) -> GameVersion:
        """Fetch a single game version by its code (e.g. ``"4.0.0-LIVE.123"``).

        Raises :class:`NotFoundError` if no such version exists.
        """
        payload = await self._client.get(f"{_BASE}/{version.strip()}")
        data = extract_data(payload)
        if not data:
            raise NotFoundError(f"No game version found for {version!r}")
        return GameVersion.from_api(data, self._locale)

    async def get_default(self) -> GameVersion:
        """Fetch the current default (live) game version."""
        payload = await self._client.get(f"{_BASE}/default")
        data = extract_data(payload)
        if not data:
            raise NotFoundError("No default game version found")
        return GameVersion.from_api(data, self._locale)

    async def get_changelog(self, version: str) -> dict[str, Any]:
        """Fetch the raw changelog for a game version.

        Returns the decoded JSON payload as-is; the changelog shape varies
        by version and is not modelled as a dataclass.
        """
        return await self._client.get(f"{_BASE}/{version.strip()}/changelog")

    async def search(self, query: str | None = None, *, limit: int = 25) -> list[GameVersion]:
        """List game versions, optionally filtered by channel or version code."""
        params: dict[str, Any] = {"page[size]": min(limit, 200)}
        if query:
            params["filter[code]"] = query.strip()
        payload = await self._client.get(_BASE, params=params)
        raw = extract_data(payload, [])
        return [GameVersion.from_api(item, self._locale) for item in raw]
