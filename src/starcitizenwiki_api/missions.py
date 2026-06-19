from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.starcitizenwiki_api._common import DEFAULT_LOCALE, MAX_PAGE_SIZE, extract_data
from src.starcitizenwiki_api.client import NotFoundError, StarCitizenWikiClient

_BASE = "https://api.star-citizen.wiki/api/missions"

DEFAULT_PAGE_SIZE = 25
DEFAULT_SORT = "title"


@dataclass(frozen=True)
class BlueprintStub:
    name: str
    uuid: str
    link: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> BlueprintStub:
        return cls(
            name=data.get("name") or "Unknown",
            uuid=data.get("uuid") or "",
            link=data.get("link") or "",
        )


@dataclass(frozen=True)
class ReputationGain:
    faction: str
    faction_uuid: str
    scope: str | None
    tier: str | None
    amount: int | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ReputationGain:
        return cls(
            faction=data.get("faction") or "",
            faction_uuid=data.get("faction_uuid") or "",
            scope=data.get("scope"),
            tier=data.get("tier"),
            amount=data.get("amount"),
        )


@dataclass(frozen=True)
class Mission:
    uuid: str
    title: str
    description: str | None
    mission_type: str | None
    mission_giver: str | None
    faction_name: str | None
    rank_index: int | None
    illegal: bool
    legality_label: str | None
    shareable: bool
    once_only: bool
    has_combat: bool
    enemy_count_min: int | None
    enemy_count_max: int | None
    reward_min: int | None
    reward_max: int | None
    reward_currency: str | None
    reward_scope: str | None
    time_to_complete_minutes: float | None
    star_systems: tuple[str, ...]
    has_blueprints: bool
    has_chain: bool
    has_prerequisites: bool
    max_players_per_instance: int | None
    cooldown_label: str | None
    reputation_amount: int | None
    web_url: str | None
    reputation_gained: list[ReputationGain] = field(default_factory=list)
    blueprints: list[BlueprintStub] = field(default_factory=list)

    @property
    def slug(self) -> str | None:
        return self.uuid or None

    @property
    def name(self) -> str:
        return self.title

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = DEFAULT_LOCALE) -> Mission:
        faction = data.get("faction") or {}
        return cls(
            uuid=data.get("uuid") or "",
            title=data.get("title") or "Unknown",
            description=data.get("description"),
            mission_type=data.get("mission_type"),
            mission_giver=data.get("mission_giver"),
            faction_name=faction.get("name") if isinstance(faction, dict) else None,
            rank_index=data.get("rank_index"),
            illegal=bool(data.get("illegal")),
            legality_label=data.get("legality_label"),
            shareable=bool(data.get("shareable")),
            once_only=bool(data.get("once_only")),
            has_combat=bool(data.get("has_combat")),
            enemy_count_min=data.get("enemy_count_min"),
            enemy_count_max=data.get("enemy_count_max"),
            reward_min=data.get("reward_min"),
            reward_max=data.get("reward_max"),
            reward_currency=data.get("reward_currency"),
            reward_scope=data.get("reward_scope"),
            time_to_complete_minutes=data.get("time_to_complete_minutes"),
            star_systems=tuple(data.get("star_systems") or []),
            has_blueprints=bool(data.get("has_blueprints")),
            has_chain=bool(data.get("has_chain")),
            has_prerequisites=bool(data.get("has_prerequisites")),
            max_players_per_instance=data.get("max_players_per_instance"),
            cooldown_label=data.get("cooldown_label"),
            reputation_amount=data.get("reputation_amount"),
            web_url=data.get("web_url"),
            reputation_gained=[
                ReputationGain.from_api(r)
                for r in (data.get("reputation_gained") or [])
                if isinstance(r, dict)
            ],
            blueprints=[
                BlueprintStub.from_api(b)
                for b in (data.get("blueprints") or [])
                if isinstance(b, dict)
            ],
        )


class Missions:
    """Missions from the star-citizen.wiki API (``/api/missions``)."""

    def __init__(self, client: StarCitizenWikiClient, *, locale: str = DEFAULT_LOCALE) -> None:
        self._client = client
        self._locale = locale

    async def get(self, slug_or_uuid: str) -> Mission:
        """Fetch a single mission by slug or UUID.

        Raises :class:`NotFoundError` if no such mission exists.
        """
        payload = await self._client.get(f"{_BASE}/{slug_or_uuid.strip()}")
        data = extract_data(payload)
        if not data:
            raise NotFoundError(f"No mission found for {slug_or_uuid!r}")
        return Mission.from_api(data, self._locale)

    async def find(self, query: str) -> Mission | None:
        """Best-effort single match: searches by title and returns the top result."""
        results = await self.search(query, limit=5)
        if not results:
            return None
        lowered = query.strip().lower()
        return next((m for m in results if m.title.lower() == lowered), results[0])

    async def search(
        self,
        query: str | None = None,
        *,
        limit: int | None = None,
        title: str | None = None,
        mission_giver: str | None = None,
        faction: str | None = None,
        star_system: str | None = None,
        illegal: bool | None = None,
        shareable: bool | None = None,
        once_only: bool | None = None,
        has_combat: bool | None = None,
        has_blueprints: bool | None = None,
        has_prerequisites: bool | None = None,
        available_in_prison: bool | None = None,
        rank_index: int | None = None,
        reward_min: int | None = None,
        reward_max: int | None = None,
        reward_scope: str | None = None,
        sort: str = DEFAULT_SORT,
        page_size: int = DEFAULT_PAGE_SIZE,
        version: str | None = None,
    ) -> list[Mission]:
        """Search and filter missions.

        All parameters are optional and map to the API query params:

        - ``query`` — search across title, description, and debug name (``filter[query]``)
        - ``title`` — partial title match (``filter[title]``)
        - ``mission_giver`` — NPC name match (``filter[mission_giver]``)
        - ``faction`` — faction name; comma-separated for multiple (``filter[faction]``)
        - ``star_system`` — system name (``filter[star_system]``)
        - ``illegal`` — filter by legality flag (``filter[illegal]``)
        - ``shareable`` — filter by share flag (``filter[shareable]``)
        - ``once_only`` — filter by one-time missions (``filter[once_only]``)
        - ``has_combat`` — filter by combat presence (``filter[has_combat]``)
        - ``has_blueprints`` — filter missions that drop blueprints (``filter[has_blueprints]``)
        - ``has_prerequisites`` — filter gated missions (``filter[has_prerequisites]``)
        - ``available_in_prison`` — filter prison missions (``filter[available_in_prison]``)
        - ``rank_index`` — difficulty rank integer (``filter[rank_index]``)
        - ``reward_min`` — minimum aUEC reward (``filter[reward_min]``)
        - ``reward_max`` — maximum aUEC reward (``filter[reward_max]``)
        - ``reward_scope`` — reward category label (``filter[reward_scope]``)
        - ``sort`` — sort field, prefix ``-`` for descending; supports ``title``,
          ``rank_index``, ``reward_min``, ``reward_max``, ``time_to_complete_minutes``,
          ``max_players_per_instance``, ``reputation_amount`` (default: ``title``)
        - ``page_size`` — results per page, max 200 (default: 25)
        - ``version`` — game version code; omit to use the API default
        """
        effective_size = limit if limit is not None else page_size
        params: dict[str, Any] = {
            "page[size]": min(effective_size, MAX_PAGE_SIZE),
            "sort": sort,
        }
        if query is not None:
            params["filter[query]"] = query
        if title is not None:
            params["filter[title]"] = title
        if mission_giver is not None:
            params["filter[mission_giver]"] = mission_giver
        if faction is not None:
            params["filter[faction]"] = faction
        if star_system is not None:
            params["filter[star_system]"] = star_system
        if illegal is not None:
            params["filter[illegal]"] = str(illegal).lower()
        if shareable is not None:
            params["filter[shareable]"] = str(shareable).lower()
        if once_only is not None:
            params["filter[once_only]"] = str(once_only).lower()
        if has_combat is not None:
            params["filter[has_combat]"] = str(has_combat).lower()
        if has_blueprints is not None:
            params["filter[has_blueprints]"] = str(has_blueprints).lower()
        if has_prerequisites is not None:
            params["filter[has_prerequisites]"] = str(has_prerequisites).lower()
        if available_in_prison is not None:
            params["filter[available_in_prison]"] = str(available_in_prison).lower()
        if rank_index is not None:
            params["filter[rank_index]"] = rank_index
        if reward_min is not None:
            params["filter[reward_min]"] = reward_min
        if reward_max is not None:
            params["filter[reward_max]"] = reward_max
        if reward_scope is not None:
            params["filter[reward_scope]"] = reward_scope
        if version is not None:
            params["version"] = version

        payload = await self._client.get(_BASE, params=params)
        raw = extract_data(payload, [])
        return [Mission.from_api(item, self._locale) for item in raw]
