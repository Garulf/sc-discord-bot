from discord import AppCommandOptionType

from src.commands.beacons import BeaconsCog
from src.commands.beacons.categories import CATEGORIES

_CASCADE_CATEGORIES = ("mining", "medic", "squad", "backup", "salvage", "escort", "transport", "contested")


def _params(name):
    return {p.name: p for p in BeaconsCog.beacon.get_command(name).parameters}


def test_beacon_group_is_guild_only():
    assert BeaconsCog.beacon.guild_only is True


def test_every_category_has_a_command():
    names = {cmd.name for cmd in BeaconsCog.beacon.commands}
    assert set(CATEGORIES) <= names


def test_cascade_categories_take_system_planet_location():
    for name in _CASCADE_CATEGORIES:
        params = _params(name)
        assert {"system", "planet", "location"} <= set(params)
        assert params["system"].required is True
        assert params["planet"].required is False
        assert params["location"].required is False


def test_choice_fields_expose_their_declared_choices():
    for category in CATEGORIES.values():
        params = _params(category.key)
        for spec in category.fields:
            if spec.kind == "choice":
                values = [choice.value for choice in params[spec.key].choices]
                assert values == list(spec.choices)


def test_int_fields_are_integer_options():
    assert _params("squad")["size"].type is AppCommandOptionType.integer
    assert _params("cargo")["scu"].type is AppCommandOptionType.integer


def test_escort_and_transport_take_optional_destination():
    for name in ("escort", "transport"):
        params = _params(name)
        assert params["destination"].required is False
        assert params["destination"].type is AppCommandOptionType.string


def test_role_category_choices_track_categories():
    params = _params("role")
    assert [(c.name, c.value) for c in params["category"].choices] == [(c.label, c.key) for c in CATEGORIES.values()]


def test_cargo_keeps_single_route_fields():
    command = BeaconsCog.beacon.get_command("cargo")
    display_names = {p.display_name for p in command.parameters}
    assert {"route-from", "route-to"} <= display_names
    assert "system" not in {p.name for p in command.parameters}


def test_cog_load_registers_current_and_legacy_views_and_migrates():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from src.commands import beacons as pkg

    migrate = AsyncMock()
    original = pkg.store.migrate_legacy_keys
    pkg.store.migrate_legacy_keys = migrate
    try:
        bot = MagicMock()
        bot.add_view = MagicMock()
        bot.state.keys = AsyncMock(return_value=[])
        bot.tree.fetch_commands = AsyncMock(return_value=[])
        cog = BeaconsCog(bot)
        asyncio.run(cog.cog_load())
    finally:
        pkg.store.migrate_legacy_keys = original
    custom_ids = {item.custom_id for call in bot.add_view.call_args_list for item in call.args[0].children}
    assert bot.add_view.call_count == 4
    assert "beacons:claim" in custom_ids
    assert "tickets:claim" in custom_ids
    migrate.assert_awaited_once_with(bot.state)
