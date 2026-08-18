from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import board
from src.commands.beacons.rules import STATUS_ACTIVE, STATUS_OPEN


def _beacon(**overrides):
    beacon = {
        "guild_id": 1,
        "category": "medic",
        "requester_id": 1,
        "members": [],
        "status": STATUS_OPEN,
        "opened_at": 0.0,
        "closed_at": None,
        "closed_by_id": None,
        "fields": {"location": "Stanton"},
        "last_activity_at": 0.0,
        "first_joined_at": None,
        "warned_at": None,
        "escalated_at": None,
        "voice_channel_id": None,
        "commended": False,
        "nudged": [],
    }
    beacon.update(overrides)
    return beacon


def test_build_board_embed_empty():
    embed = board.build_board_embed([])
    assert embed.title == "Beacon Board"
    assert embed.description == "No open beacons."


def test_build_board_embed_groups_active_before_open_sorted_by_opened_at():
    open_early = _beacon(category="medic", status=STATUS_OPEN, opened_at=10.0)
    open_late = _beacon(category="medic", status=STATUS_OPEN, opened_at=20.0)
    active_early = _beacon(category="mining", status=STATUS_ACTIVE, opened_at=5.0)
    active_late = _beacon(category="mining", status=STATUS_ACTIVE, opened_at=15.0)
    entries = [
        (200, open_late),
        (100, open_early),
        (400, active_late),
        (300, active_early),
    ]
    embed = board.build_board_embed(entries)
    lines = embed.description.split("\n")
    assert lines == [
        "\N{PICK} <#300> - Active",
        "\N{PICK} <#400> - Active",
        "\N{ADHESIVE BANDAGE} <#100> - Open",
        "\N{ADHESIVE BANDAGE} <#200> - Open",
    ]


def test_build_board_embed_falls_back_to_default_emoji_for_unknown_category():
    unknown = _beacon(category="ticket-legacy", status=STATUS_OPEN, opened_at=1.0)
    embed = board.build_board_embed([(100, unknown)])
    assert embed.description == "\N{ROUND PUSHPIN} <#100> - Open"


@pytest.fixture
def make_cog(monkeypatch):
    def _make(config=None, entries=None):
        cog = MagicMock()
        cog.bot.state = MagicMock()
        monkeypatch.setattr(board.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(board.store, "set_config", AsyncMock())
        monkeypatch.setattr(board.store, "open_beacons", AsyncMock(return_value=entries or []))
        return cog

    return _make


def _guild(channel=None):
    guild = MagicMock()
    guild.id = 1
    guild.get_channel = MagicMock(return_value=channel)
    return guild


@pytest.mark.asyncio
async def test_refresh_board_no_config_returns(make_cog):
    cog = make_cog(config=None)
    guild = _guild()
    await board.refresh_board(cog, guild)
    board.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_board_no_board_key_returns(make_cog):
    cog = make_cog(config={"roles": {}})
    guild = _guild()
    await board.refresh_board(cog, guild)
    board.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_board_channel_missing_returns(make_cog):
    config = {"board": {"channel_id": 5, "message_id": 6}}
    cog = make_cog(config=config)
    guild = _guild(channel=None)
    await board.refresh_board(cog, guild)
    board.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_board_edits_message(make_cog):
    config = {"board": {"channel_id": 5, "message_id": 6}}
    beacon = _beacon()
    cog = make_cog(config=config, entries=[(99, beacon)])
    partial = MagicMock()
    partial.edit = AsyncMock()
    channel = MagicMock()
    channel.get_partial_message = MagicMock(return_value=partial)
    guild = _guild(channel=channel)
    await board.refresh_board(cog, guild)
    channel.get_partial_message.assert_called_once_with(6)
    partial.edit.assert_awaited_once()
    embed = partial.edit.await_args.kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    board.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_board_uses_prefetched_entries_without_scanning(make_cog):
    config = {"board": {"channel_id": 5, "message_id": 6}}
    cog = make_cog(config=config)
    partial = MagicMock()
    partial.edit = AsyncMock()
    channel = MagicMock()
    channel.get_partial_message = MagicMock(return_value=partial)
    guild = _guild(channel=channel)
    await board.refresh_board(cog, guild, entries=[(99, _beacon())])
    board.store.open_beacons.assert_not_awaited()
    partial.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_board_not_found_clears_config(make_cog):
    config = {"board": {"channel_id": 5, "message_id": 6}, "roles": {}}
    cog = make_cog(config=config)
    partial = MagicMock()
    partial.edit = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "gone"))
    channel = MagicMock()
    channel.get_partial_message = MagicMock(return_value=partial)
    guild = _guild(channel=channel)
    await board.refresh_board(cog, guild)
    board.store.set_config.assert_awaited_once()
    saved = board.store.set_config.await_args.args[2]
    assert "board" not in saved


@pytest.mark.asyncio
async def test_refresh_board_other_http_exception_is_logged_not_raised(make_cog):
    config = {"board": {"channel_id": 5, "message_id": 6}}
    cog = make_cog(config=config)
    partial = MagicMock()
    partial.edit = AsyncMock(side_effect=discord.HTTPException(MagicMock(status=500), "boom"))
    channel = MagicMock()
    channel.get_partial_message = MagicMock(return_value=partial)
    guild = _guild(channel=channel)
    await board.refresh_board(cog, guild)
    board.store.set_config.assert_not_awaited()


def _interaction(channel):
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.channel = channel
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_handle_board_install_requires_config(make_cog):
    cog = make_cog(config=None)
    interaction = _interaction(MagicMock(spec=discord.TextChannel))
    await board.handle_board(cog, interaction, "install")
    message = interaction.response.send_message.await_args.args[0]
    assert "setup" in message


@pytest.mark.asyncio
async def test_handle_board_install_requires_text_channel(make_cog):
    cog = make_cog(config={"roles": {}})
    interaction = _interaction(MagicMock(spec=discord.Thread))
    await board.handle_board(cog, interaction, "install")
    message = interaction.response.send_message.await_args.args[0]
    assert "text channel" in message
    board.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_board_install_posts_and_saves(make_cog):
    config = {"roles": {}}
    cog = make_cog(config=config)
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 10
    message = MagicMock()
    message.id = 20
    channel.send = AsyncMock(return_value=message)
    interaction = _interaction(channel)
    await board.handle_board(cog, interaction, "install")
    channel.send.assert_awaited_once()
    board.store.set_config.assert_awaited_once()
    saved = board.store.set_config.await_args.args[2]
    assert saved["board"] == {"channel_id": 10, "message_id": 20}
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_board_install_deletes_previous_board_message(make_cog):
    old_message = MagicMock()
    old_message.delete = AsyncMock()
    old_channel = MagicMock()
    old_channel.get_partial_message = MagicMock(return_value=old_message)
    config = {"roles": {}, "board": {"channel_id": 5, "message_id": 6}}
    cog = make_cog(config=config)
    cog.bot.get_guild = MagicMock()

    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 10
    new_message = MagicMock()
    new_message.id = 20
    channel.send = AsyncMock(return_value=new_message)
    interaction = _interaction(channel)
    interaction.guild.get_channel = MagicMock(return_value=old_channel)
    await board.handle_board(cog, interaction, "install")
    old_channel.get_partial_message.assert_called_once_with(6)
    old_message.delete.assert_awaited_once()
    saved = board.store.set_config.await_args.args[2]
    assert saved["board"] == {"channel_id": 10, "message_id": 20}


@pytest.mark.asyncio
async def test_handle_board_remove_no_board_installed(make_cog):
    cog = make_cog(config={"roles": {}})
    interaction = _interaction(MagicMock(spec=discord.TextChannel))
    await board.handle_board(cog, interaction, "remove")
    message = interaction.response.send_message.await_args.args[0]
    assert "No" in message
    board.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_board_remove_deletes_message_and_clears_config(make_cog):
    old_message = MagicMock()
    old_message.delete = AsyncMock()
    old_channel = MagicMock()
    old_channel.get_partial_message = MagicMock(return_value=old_message)
    config = {"roles": {}, "board": {"channel_id": 5, "message_id": 6}}
    cog = make_cog(config=config)
    interaction = _interaction(MagicMock(spec=discord.TextChannel))
    interaction.guild.get_channel = MagicMock(return_value=old_channel)
    await board.handle_board(cog, interaction, "remove")
    old_message.delete.assert_awaited_once()
    board.store.set_config.assert_awaited_once()
    saved = board.store.set_config.await_args.args[2]
    assert "board" not in saved
    message = interaction.response.send_message.await_args.args[0]
    assert "removed" in message.lower()
