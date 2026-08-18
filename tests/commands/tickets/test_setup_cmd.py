from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.tickets import setup_cmd


def _admin_interaction(channel):
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.channel = channel
    interaction.response.send_message = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_setup_in_text_channel_posts_panel_and_saves_thread_config(monkeypatch):
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=None))
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 10
    message = MagicMock()
    message.id = 11
    channel.send = AsyncMock(return_value=message)
    cog = MagicMock()
    interaction = _admin_interaction(channel)
    await setup_cmd.handle_setup(cog, interaction)
    channel.send.assert_awaited_once()
    assert saved["mode"] == "thread"
    assert saved["channel_id"] == 10
    assert saved["panel_message_id"] == 11
    assert saved["roles"] == {}


@pytest.mark.asyncio
async def test_setup_preserves_existing_role_mapping(monkeypatch):
    saved = {}
    old = {"channel_id": 1, "mode": "thread", "panel_message_id": 2, "tag_ids": {}, "roles": {"medic": 5}}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=old))
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 10
    message = MagicMock()
    message.id = 11
    channel.send = AsyncMock(return_value=message)
    await setup_cmd.handle_setup(MagicMock(), _admin_interaction(channel))
    assert saved["roles"] == {"medic": 5}


@pytest.mark.asyncio
async def test_role_requires_setup(monkeypatch):
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=None))
    interaction = _admin_interaction(MagicMock())
    await setup_cmd.handle_role(MagicMock(), interaction, "medic", MagicMock())
    assert "setup" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_role_saves_mapping(monkeypatch):
    saved = {}
    config = {"channel_id": 1, "mode": "thread", "panel_message_id": 2, "tag_ids": {}, "roles": {}}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    role = MagicMock()
    role.id = 77
    interaction = _admin_interaction(MagicMock())
    await setup_cmd.handle_role(MagicMock(), interaction, "medic", role)
    assert saved["roles"]["medic"] == 77


def test_cog_defines_all_ticket_commands():
    from src.commands.tickets import TicketsCog

    names = {cmd.name for cmd in TicketsCog.ticket.commands}
    assert {"setup", "role", "mining", "medic", "squad", "backup", "cargo", "salvage"} <= names
