from src.commands.beacons import BeaconsCog

_SPLIT_CATEGORIES = ("mining", "medic", "squad", "backup", "salvage")


def test_beacon_group_is_guild_only():
    assert BeaconsCog.beacon.guild_only is True


def test_split_categories_take_system_planet_location():
    for name in _SPLIT_CATEGORIES:
        command = BeaconsCog.beacon.get_command(name)
        params = {p.name: p for p in command.parameters}
        assert {"system", "planet", "location"} <= set(params)
        assert params["system"].required is True
        assert params["planet"].required is False
        assert params["location"].required is False


def test_cargo_keeps_single_route_fields():
    command = BeaconsCog.beacon.get_command("cargo")
    display_names = {p.display_name for p in command.parameters}
    assert {"route-from", "route-to"} <= display_names
    assert "system" not in {p.name for p in command.parameters}
