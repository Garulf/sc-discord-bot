from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.beacons.location import (
    FLYABLE_SYSTEMS,
    format_breadcrumb,
    location_autocomplete,
    parse_location,
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


def _poi(name, system, parent, type_):
    obj = MagicMock()
    obj.name = name
    obj.star_system_name = system
    obj.parent_name = parent
    obj.type = type_
    return obj


_HURSTON = _poi("Hurston", "Stanton", "Stanton", "Planet")
_LORVILLE = _poi("Lorville", "Stanton", "Hurston", "Settlement")
_BLOOM = _poi("Bloom", "Pyro", "Pyro", "Planet")
_LOREVILLE = _poi("Lore Outpost", "Oberon", "Uriel", "Outpost")


def _interaction(pois=None):
    interaction = MagicMock()
    interaction.client.locations_api.search = AsyncMock(return_value=list(pois or []))
    return interaction


@pytest.mark.asyncio
async def test_autocomplete_spans_systems_bodies_and_pois():
    interaction = _interaction(pois=[_HURSTON, _LORVILLE])
    choices = await location_autocomplete(interaction, "s")
    values = [c.value for c in choices]
    assert "Stanton" in values
    assert "Stanton:Hurston" in values
    assert "Stanton:Hurston:Lorville" in values


@pytest.mark.asyncio
async def test_autocomplete_empty_query_offers_flyable_systems():
    interaction = _interaction()
    choices = await location_autocomplete(interaction, "")
    assert [c.value for c in choices][: len(FLYABLE_SYSTEMS)] == list(FLYABLE_SYSTEMS)


@pytest.mark.asyncio
async def test_autocomplete_excludes_non_flyable_systems():
    interaction = _interaction(pois=[_LOREVILLE, _BLOOM])
    choices = await location_autocomplete(interaction, "o")
    values = [c.value for c in choices]
    assert "Pyro:Bloom" in values
    assert all("Oberon" not in v for v in values)


@pytest.mark.asyncio
async def test_autocomplete_drops_uninitialized_pois():
    ghost = _poi("<= UNINITIALIZED =>", "Stanton", "Hurston", "Outpost")
    interaction = _interaction(pois=[ghost, _LORVILLE])
    choices = await location_autocomplete(interaction, "lor")
    values = [c.value for c in choices]
    assert "Stanton:Hurston:Lorville" in values
    assert all("UNINITIALIZED" not in v for v in values)


@pytest.mark.asyncio
async def test_autocomplete_degrades_uninitialized_parent_to_system_name():
    orphan = _poi("Lost Outpost", "Stanton", "<= UNINITIALIZED =>", "Outpost")
    interaction = _interaction(pois=[orphan])
    choices = await location_autocomplete(interaction, "lost")
    values = [c.value for c in choices]
    assert "Stanton:Lost Outpost" in values
    assert all("UNINITIALIZED" not in v for v in values)


@pytest.mark.asyncio
async def test_autocomplete_swallows_api_errors():
    interaction = _interaction()
    interaction.client.locations_api.search = AsyncMock(side_effect=RuntimeError("api down"))
    choices = await location_autocomplete(interaction, "lor")
    assert [c.value for c in choices] == []
