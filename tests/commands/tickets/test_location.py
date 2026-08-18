from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.tickets.location import format_breadcrumb, location_autocomplete, parse_location


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


def _named(name, system=None, parent=None):
    obj = MagicMock()
    obj.name = name
    obj.star_system_name = system
    obj.parent_name = parent
    return obj


@pytest.mark.asyncio
async def test_autocomplete_builds_colon_paths():
    interaction = MagicMock()
    client = interaction.client
    client.starsystems_api.search = AsyncMock(return_value=[_named("Stanton")])
    client.celestial_objects_api.search = AsyncMock(return_value=[_named("Hurston", system="Stanton")])
    client.locations_api.search = AsyncMock(return_value=[_named("Lorville", system="Stanton", parent="Hurston")])
    choices = await location_autocomplete(interaction, "lor")
    values = [c.value for c in choices]
    assert "Stanton" in values
    assert "Stanton:Hurston" in values
    assert "Stanton:Hurston:Lorville" in values


@pytest.mark.asyncio
async def test_autocomplete_searches_last_segment():
    interaction = MagicMock()
    client = interaction.client
    client.starsystems_api.search = AsyncMock(return_value=[])
    client.celestial_objects_api.search = AsyncMock(return_value=[])
    client.locations_api.search = AsyncMock(return_value=[])
    await location_autocomplete(interaction, "Stanton:Hurston:Lor")
    client.locations_api.search.assert_awaited_once_with("Lor")


@pytest.mark.asyncio
async def test_autocomplete_swallows_api_errors():
    interaction = MagicMock()
    client = interaction.client
    client.starsystems_api.search = AsyncMock(side_effect=RuntimeError("api down"))
    client.celestial_objects_api.search = AsyncMock(side_effect=RuntimeError("api down"))
    client.locations_api.search = AsyncMock(side_effect=RuntimeError("api down"))
    assert await location_autocomplete(interaction, "lor") == []
