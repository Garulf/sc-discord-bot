from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, extract_data
from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient

_BASE = "https://api.star-citizen.wiki/api/stats"


@dataclass(frozen=True)
class SCStats:
    fans: int | None
    funds: float | None
    fleet: int | None
    timestamp: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> SCStats:
        funds_raw = data.get("funds")
        try:
            funds = float(funds_raw) if funds_raw is not None else None
        except (ValueError, TypeError):
            funds = None
        return cls(
            fans=data.get("fans"),
            funds=funds,
            fleet=data.get("fleet"),
            timestamp=data.get("timestamp"),
        )


class Stats:
    """Crowdfunding statistics from the star-citizen.wiki API (``/api/stats``)."""

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get_latest(self) -> SCStats:
        """Fetch the most recent crowdfunding snapshot."""
        payload = await self._client.get(f"{_BASE}/latest")
        data = extract_data(payload)
        if not data:
            raise NotFoundError("No stats data returned")
        return SCStats.from_api(data, self._locale)

    async def get_all(self, *, limit: int = 25) -> list[SCStats]:
        """Fetch a page of historical crowdfunding snapshots, newest first."""
        payload = await self._client.get(_BASE, params={"page[size]": min(limit, 200)})
        raw = extract_data(payload, [])
        return [SCStats.from_api(item, self._locale) for item in raw]
