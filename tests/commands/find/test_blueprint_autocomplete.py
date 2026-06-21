"""Tests for blueprint autocomplete deduplication."""

from __future__ import annotations

import pytest

from src.commands.find.blueprint import autocomplete
from src.starcitizenwiki_api.blueprints import Blueprint


def _blueprint(name: str, uuid: str) -> Blueprint:
    return Blueprint(
        uuid=uuid,
        name=name,
        web_url=None,
        key=None,
        craft_time_seconds=None,
        craft_time_label=None,
        ingredient_count=None,
        unlocking_missions_count=None,
        is_available_by_default=None,
        output_class=None,
        output_type=None,
        output_type_label=None,
    )


class _FakeAPI:
    def __init__(self, blueprints: list[Blueprint]) -> None:
        self._blueprints = blueprints

    async def search(self, *, query=None, page_size=25, **_):
        return self._blueprints[:page_size]


class _FakeCog:
    def __init__(self, blueprints: list[Blueprint]) -> None:
        self.bot = type("Bot", (), {"blueprints_api": _FakeAPI(blueprints)})()


async def _run(blueprints: list[Blueprint], current: str = "") -> list:
    return await autocomplete(_FakeCog(blueprints), current)


class TestBlueprintAutocomplete:
    async def test_deduplicates_by_name(self):
        blueprints = [
            _blueprint("Tigerstreik S3 Repeater", "uuid-1"),
            _blueprint("Tigerstreik S3 Repeater", "uuid-2"),
            _blueprint("Unique Blueprint", "uuid-3"),
        ]
        choices = await _run(blueprints)
        names = [c.name for c in choices]
        assert names.count("Tigerstreik S3 Repeater") == 1

    async def test_unique_names_all_shown(self):
        blueprints = [_blueprint(f"Blueprint {i}", f"uuid-{i}") for i in range(5)]
        choices = await _run(blueprints)
        assert len(choices) == 5

    async def test_sorted_shortest_first(self):
        blueprints = [
            _blueprint("A Very Long Blueprint Name", "uuid-1"),
            _blueprint("Short", "uuid-2"),
        ]
        choices = await _run(blueprints)
        assert choices[0].name == "Short"

    async def test_capped_at_max_choices(self):
        blueprints = [_blueprint(f"Blueprint {i:03d}", f"uuid-{i}") for i in range(30)]
        choices = await _run(blueprints)
        assert len(choices) == 25

    async def test_value_is_uuid(self):
        blueprints = [_blueprint("Some Blueprint", "my-uuid")]
        choices = await _run(blueprints)
        assert choices[0].value == "my-uuid"

    async def test_api_error_returns_empty(self):
        class _ErrorAPI:
            async def search(self, **_):
                raise RuntimeError("boom")

        cog = type("Cog", (), {"bot": type("Bot", (), {"blueprints_api": _ErrorAPI()})()})()
        assert await autocomplete(cog, "") == []
