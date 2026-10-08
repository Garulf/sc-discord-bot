from unittest.mock import AsyncMock, MagicMock

from src.commands.checks import admin_or_sc_bot
from src.commands.manifest import ManifestCog, store


def _command(path):
    group = ManifestCog.manifest
    *parents, name = path.split()
    for parent in parents:
        group = group.get_command(parent)
    return group.get_command(name)


def test_group_is_guild_only():
    assert ManifestCog.manifest.guild_only is True


def test_command_surface():
    names = {cmd.qualified_name for cmd in ManifestCog.manifest.walk_commands() if hasattr(cmd, "callback")}
    assert names == {"manifest new", "manifest list", "manifest owed", "manifest delete", "manifest config channel"}


def test_delete_autocompletes_manifest():
    params = {p.name: p for p in _command("delete").parameters}
    assert params["manifest"].autocomplete


def test_officer_commands_are_checked():
    for path in ("delete", "config channel"):
        assert admin_or_sc_bot in _command(path).checks


async def test_cog_load_registers_views_and_purges_loot(monkeypatch):
    purge = AsyncMock(return_value=3)
    monkeypatch.setattr(store, "purge_legacy_loot", purge)
    bot = MagicMock()
    cog = ManifestCog(bot)
    await cog.cog_load()
    assert bot.add_view.call_count == 2
    assert cog.card_view is not None
    assert cog.log_view is not None
    purge.assert_awaited_once_with(bot.state)


def test_extension_is_loaded():
    from src.bot import INITIAL_EXTENSIONS

    assert "src.commands.manifest" in INITIAL_EXTENSIONS
    assert "src.commands.loot" not in INITIAL_EXTENSIONS
