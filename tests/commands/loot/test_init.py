from unittest.mock import MagicMock

import pytest
from discord import AppCommandOptionType

from src.commands.checks import admin_or_sc_bot
from src.commands.loot import LootCog


def _command(path):
    group = LootCog.loot
    *parents, name = path.split()
    for parent in parents:
        group = group.get_command(parent)
    return group.get_command(name)


def _params(path):
    return {p.name: p for p in _command(path).parameters}


def test_group_is_guild_only():
    assert LootCog.loot.guild_only is True


def test_command_surface():
    names = {cmd.qualified_name for cmd in LootCog.loot.walk_commands()}
    assert {
        "loot new", "loot log", "loot sell", "loot paid", "loot dispute", "loot undo", "loot holder",
        "loot delete", "loot owed", "loot list", "loot participants add", "loot participants remove",
        "loot cargo fix", "loot config channel",
    } <= names


def test_sell_options():
    params = _params("sell")
    assert all(params[name].required for name in ("raid", "commodity", "scu", "total"))
    assert params["scu"].type is AppCommandOptionType.integer
    assert params["total"].type is AppCommandOptionType.integer
    assert params["raid"].autocomplete
    assert params["commodity"].autocomplete


def test_new_options():
    params = _params("new")
    assert params["participants"].required is False
    assert params["holder"].type is AppCommandOptionType.user


def test_admin_commands_are_checked():
    for path in ("delete", "config channel"):
        assert admin_or_sc_bot in _command(path).checks


@pytest.mark.asyncio
async def test_cog_load_registers_persistent_views():
    bot = MagicMock()
    cog = LootCog(bot)
    await cog.cog_load()
    assert bot.add_view.call_count == 2
    assert cog.card_view is not None
    assert cog.log_view is not None


def test_extension_is_loaded():
    from src.bot import INITIAL_EXTENSIONS

    assert "src.commands.loot" in INITIAL_EXTENSIONS
