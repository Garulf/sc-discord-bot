from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.beacons.location import (
    FLYABLE_SYSTEMS,
    combine_location,
    format_breadcrumb,
    parse_location,
    planet_autocomplete,
    poi_autocomplete,
    route_autocomplete,
    system_autocomplete,
)


def test_parse_full_location():
    assert parse_location("Stanton:Hurston:Lorville") == ("Stanton", "Hurston", "Lorville")


def test_parse_partial_locations():
    assert parse_location("Pyro:Bloom") == ("Pyro", "Bloom")
    assert parse_location("Stanton") == ("Stanton",)


def test_parse_strips_whitespace():
    assert parse_location(" Stanton : Hurston ") == ("Stanton", "Hurston")


def test_parse_rejects_bad_input():
    assert parse_location("") is None
    assert parse_location("a:b:c:d") is None
    assert parse_location("Stanton::Lorville") is None
    assert parse_location(":") is None


def test_format_breadcrumb():
    assert format_breadcrumb("Stanton:Hurston:Lorville") == "Stanton › Hurston › Lorville"
    assert format_breadcrumb("Stanton") == "Stanton"


def test_combine_location_joins_present_parts():
    assert combine_location("Stanton", "Hurston", "Lorville") == "Stanton:Hurston:Lorville"
    assert combine_location("Stanton", None, None) == "Stanton"
    assert combine_location("Stanton", "Hurston", None) == "Stanton:Hurston"
    assert combine_location("Stanton", None, "Lorville") == "Stanton:Lorville"


def _poi(name, system, parent, type_):
    obj = MagicMock()
    obj.name = name
    obj.star_system_name = system
    obj.parent_name = parent
    obj.type = type_
    return obj


_HURSTON = _poi("Hurston", "Stanton", "Stanton", "Planet")
_DAYMAR = _poi("Daymar", "Stanton", "Crusader", "Moon")
_LORVILLE = _poi("Lorville", "Stanton", "Hurston", "Settlement")
_EVERUS = _poi("Everus Harbor", "Stanton", "Hurston", "Manmade")
_BLOOM = _poi("Bloom", "Pyro", "Pyro", "Planet")
_LOREVILLE = _poi("Lore Outpost", "Oberon", "Uriel", "Outpost")


def _interaction(pois=None, system=None, planet=None):
    interaction = MagicMock()
    interaction.client.locations_api.search = AsyncMock(return_value=list(pois or []))
    interaction.namespace.system = system
    interaction.namespace.planet = planet
    return interaction


@pytest.mark.asyncio
async def test_system_autocomplete_lists_flyable_systems_without_api_calls():
    interaction = _interaction()
    choices = await system_autocomplete(interaction, "")
    assert [c.value for c in choices] == list(FLYABLE_SYSTEMS)
    interaction.client.locations_api.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_system_autocomplete_filters_case_insensitively():
    choices = await system_autocomplete(_interaction(), "py")
    assert [c.value for c in choices] == ["Pyro"]


@pytest.mark.asyncio
async def test_planet_autocomplete_suggests_bodies_in_chosen_system():
    interaction = _interaction(pois=[_HURSTON, _DAYMAR, _LORVILLE, _BLOOM], system="Stanton")
    choices = await planet_autocomplete(interaction, "a")
    assert [c.value for c in choices] == ["Hurston", "Daymar"]
    interaction.client.locations_api.search.assert_awaited_once_with("a")


@pytest.mark.asyncio
async def test_planet_autocomplete_without_system_suggests_all_bodies():
    interaction = _interaction(pois=[_HURSTON, _BLOOM, _LORVILLE], system=None)
    choices = await planet_autocomplete(interaction, "b")
    assert [c.value for c in choices] == ["Hurston", "Bloom"]


@pytest.mark.asyncio
async def test_planet_autocomplete_swallows_api_errors():
    interaction = _interaction(system="Stanton")
    interaction.client.locations_api.search = AsyncMock(side_effect=RuntimeError("api down"))
    assert await planet_autocomplete(interaction, "hur") == []


@pytest.mark.asyncio
async def test_poi_autocomplete_filters_by_system_and_planet():
    interaction = _interaction(
        pois=[_HURSTON, _DAYMAR, _LORVILLE, _EVERUS, _BLOOM], system="Stanton", planet="Hurston"
    )
    choices = await poi_autocomplete(interaction, "e")
    assert [c.value for c in choices] == ["Lorville", "Everus Harbor"]


@pytest.mark.asyncio
async def test_poi_autocomplete_excludes_bodies_and_matches_case_insensitively():
    interaction = _interaction(pois=[_HURSTON, _LORVILLE, _EVERUS], system="stanton", planet=None)
    choices = await poi_autocomplete(interaction, "l")
    assert [c.value for c in choices] == ["Lorville", "Everus Harbor"]


@pytest.mark.asyncio
async def test_poi_autocomplete_swallows_api_errors():
    interaction = _interaction(system="Stanton")
    interaction.client.locations_api.search = AsyncMock(side_effect=RuntimeError("api down"))
    assert await poi_autocomplete(interaction, "lor") == []


@pytest.mark.asyncio
async def test_route_autocomplete_builds_breadcrumbs_in_flyable_systems_only():
    interaction = _interaction(pois=[_LORVILLE, _HURSTON, _LOREVILLE])
    choices = await route_autocomplete(interaction, "lor")
    values = [c.value for c in choices]
    assert "Stanton:Hurston:Lorville" in values
    assert "Stanton:Hurston" in values
    assert all("Oberon" not in v for v in values)


@pytest.mark.asyncio
async def test_route_autocomplete_swallows_api_errors():
    interaction = _interaction()
    interaction.client.locations_api.search = AsyncMock(side_effect=RuntimeError("api down"))
    assert await route_autocomplete(interaction, "lor") == []
