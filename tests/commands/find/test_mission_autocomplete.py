"""Tests for mission autocomplete deduplication."""

from __future__ import annotations

import pytest

from src.commands.find.mission import autocomplete
from src.starcitizenwiki_api.missions import Mission


def _mission(title: str, uuid: str) -> Mission:
    return Mission(
        uuid=uuid,
        title=title,
        description=None,
        mission_type=None,
        mission_giver=None,
        faction_name=None,
        rank_index=None,
        rank_label=None,
        illegal=False,
        legality_label=None,
        shareable=False,
        once_only=False,
        has_combat=False,
        enemy_count_min=None,
        enemy_count_max=None,
        reward_min=None,
        reward_max=None,
        reward_currency=None,
        reward_scope=None,
        time_to_complete_minutes=None,
        star_systems=(),
        has_blueprints=False,
        has_chain=False,
        has_prerequisites=False,
        max_players_per_instance=None,
        cooldown_label=None,
        reputation_amount=None,
        web_url=None,
    )


class _FakeAPI:
    def __init__(self, missions: list[Mission]) -> None:
        self._missions = missions

    async def search(self, query, *, limit=25):
        return self._missions[:limit]


class _FakeCog:
    def __init__(self, missions: list[Mission]) -> None:
        self.bot = type("Bot", (), {"missions_api": _FakeAPI(missions)})()


async def _run(missions: list[Mission], current: str = "") -> list:
    return await autocomplete(_FakeCog(missions), current)


class TestMissionAutocomplete:
    async def test_deduplicates_by_title(self):
        missions = [
            _mission("A Chance to Impress", "uuid-1"),
            _mission("A Chance to Impress", "uuid-2"),
            _mission("Unique Mission", "uuid-3"),
        ]
        choices = await _run(missions)
        names = [c.name for c in choices]
        assert names.count("A Chance to Impress") == 1

    async def test_unique_titles_all_shown(self):
        missions = [_mission(f"Mission {i}", f"uuid-{i}") for i in range(5)]
        choices = await _run(missions)
        assert len(choices) == 5

    async def test_sorted_shortest_first(self):
        missions = [
            _mission("A Very Long Mission Title", "uuid-1"),
            _mission("Short", "uuid-2"),
        ]
        choices = await _run(missions)
        assert choices[0].name == "Short"

    async def test_capped_at_max_choices(self):
        missions = [_mission(f"Mission {i:03d}", f"uuid-{i}") for i in range(30)]
        choices = await _run(missions)
        assert len(choices) == 25

    async def test_value_is_uuid(self):
        missions = [_mission("Some Mission", "my-uuid")]
        choices = await _run(missions)
        assert choices[0].value == "my-uuid"

    async def test_api_error_returns_empty(self):
        class _ErrorAPI:
            async def search(self, *a, **kw):
                raise RuntimeError("boom")

        cog = type("Cog", (), {"bot": type("Bot", (), {"missions_api": _ErrorAPI()})()})()
        assert await autocomplete(cog, "") == []
