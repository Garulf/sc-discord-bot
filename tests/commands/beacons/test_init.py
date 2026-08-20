from discord import AppCommandOptionType

from src.commands.beacons import BeaconsCog
from src.commands.beacons.categories import CATEGORIES
from src.commands.checks import admin_or_sc_bot

_CASCADE_CATEGORIES = ("mining", "medic", "squad", "backup", "salvage", "escort", "transport")


def _params(name):
    return {p.name: p for p in BeaconsCog.beacon.get_command(name).parameters}


def test_beacon_group_is_guild_only():
    assert BeaconsCog.beacon.guild_only is True


def test_every_category_has_a_command():
    names = {cmd.name for cmd in BeaconsCog.beacon.commands}
    assert set(CATEGORIES) <= names


def test_location_categories_take_single_required_location():
    for name in _CASCADE_CATEGORIES:
        params = _params(name)
        assert params["location"].required is True
        assert "system" not in params
        assert "planet" not in params


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


def test_mining_and_salvage_take_optional_crew():
    for name in ("mining", "salvage"):
        params = _params(name)
        assert params["crew"].required is False
        assert params["crew"].type is AppCommandOptionType.integer


def test_danger_level_is_optional_on_medic_cargo_escort():
    for name in ("medic", "cargo", "escort"):
        params = _params(name)
        assert params["danger"].required is False
        values = [choice.value for choice in params["danger"].choices]
        assert values == ["Unknown", "None", "Low", "Medium", "High"]


def test_escort_and_transport_take_optional_destination():
    for name in ("escort", "transport"):
        params = _params(name)
        assert params["destination"].required is False
        assert params["destination"].type is AppCommandOptionType.string


def test_stats_command_is_registered_and_not_admin_gated():
    command = BeaconsCog.beacon.get_command("stats")
    assert command is not None
    assert command.description == "Beacon statistics for this server"
    assert admin_or_sc_bot not in command.checks


def test_role_category_choices_track_categories():
    params = _params("role")
    assert [(c.name, c.value) for c in params["category"].choices] == [(c.label, c.key) for c in CATEGORIES.values()]


def test_contested_location_is_limited_to_contested_stations():
    from src.commands.beacons.categories import CONTESTED_STATIONS

    params = _params("contested")
    assert "system" not in params
    assert params["location"].required is True
    assert [c.value for c in params["location"].choices] == list(CONTESTED_STATIONS)


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
    assert bot.add_view.call_count == 3
    assert "beacons:claim" in custom_ids
    assert "tickets:claim" in custom_ids
    assert "beacons:commend" in custom_ids
    migrate.assert_awaited_once_with(bot.state)


def test_close_and_again_take_no_options():
    assert _params("close") == {}
    assert _params("again") == {}


def test_close_and_again_are_open_to_everyone():
    close_command = BeaconsCog.beacon.get_command("close")
    again_command = BeaconsCog.beacon.get_command("again")
    assert admin_or_sc_bot not in close_command.checks
    assert admin_or_sc_bot not in again_command.checks


def test_config_is_admin_gated():
    command = BeaconsCog.beacon.get_command("config")
    assert admin_or_sc_bot in command.checks


def test_config_options_are_all_optional():
    params = _params("config")
    for name in ("idle_warn", "idle_close", "escalate", "voice", "digest_channel", "clear_digest"):
        assert params[name].required is False


def test_config_takes_optional_voice_category_channel():
    params = _params("config")
    assert params["voice_category"].required is False
    assert params["voice_category"].display_name == "voice-category"
    assert params["voice_category"].type is AppCommandOptionType.channel
