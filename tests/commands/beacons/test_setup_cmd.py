from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import setup_cmd


def _admin_interaction(channel):
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.channel = channel
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def _forum_channel(*, id_=20, available_tags=()):
    channel = MagicMock(spec=discord.ForumChannel)
    channel.id = id_
    channel.available_tags = list(available_tags)
    return channel


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


def _wire_forum_tag_creation(channel):
    async def fake_edit(*, available_tags):
        for i, tag in enumerate(available_tags):
            if tag.id == 0:
                tag.id = 100 + i
        channel.available_tags = list(available_tags)
        return channel

    channel.edit = AsyncMock(side_effect=fake_edit)


def _wire_forum_thread_creation(channel, *, thread_id=55):
    thread = MagicMock()
    thread.id = thread_id
    thread.edit = AsyncMock()
    created = MagicMock()
    created.thread = thread
    channel.create_thread = AsyncMock(return_value=created)
    return thread


@pytest.mark.asyncio
async def test_setup_in_forum_channel_creates_tags_and_pinned_post(monkeypatch):
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=None))
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    channel = _forum_channel()
    _wire_forum_tag_creation(channel)
    _wire_forum_thread_creation(channel)
    interaction = _admin_interaction(channel)
    await setup_cmd.handle_setup(MagicMock(), interaction)
    assert saved["mode"] == "forum"
    assert saved["channel_id"] == 20
    assert saved["panel_message_id"] == 55
    expected_keys = {"mining", "medic", "squad", "backup", "cargo", "salvage", "open", "closed"}
    assert set(saved["tag_ids"]) == expected_keys
    assert all(isinstance(v, int) for v in saved["tag_ids"].values())
    tag_names = [tag.name for tag in channel.available_tags]
    assert all(len(name) <= 20 for name in tag_names)


@pytest.mark.asyncio
async def test_setup_resolves_forum_thread_to_its_parent(monkeypatch):
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=None))
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    channel = _forum_channel()
    _wire_forum_tag_creation(channel)
    _wire_forum_thread_creation(channel)
    thread = MagicMock(spec=discord.Thread)
    thread.parent = channel
    interaction = _admin_interaction(thread)
    await setup_cmd.handle_setup(MagicMock(), interaction)
    assert saved["mode"] == "forum"
    assert saved["channel_id"] == 20


@pytest.mark.asyncio
async def test_setup_accepts_explicit_channel_argument(monkeypatch):
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=None))
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    other_channel = MagicMock(spec=discord.TextChannel)
    other_channel.id = 99
    message = MagicMock()
    message.id = 111
    other_channel.send = AsyncMock(return_value=message)
    interaction = _admin_interaction(MagicMock(spec=discord.TextChannel))
    await setup_cmd.handle_setup(MagicMock(), interaction, other_channel)
    other_channel.send.assert_awaited_once()
    assert saved["channel_id"] == 99


@pytest.mark.asyncio
async def test_setup_reports_when_forum_has_no_room_for_tags(monkeypatch):
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=None))
    set_config = AsyncMock()
    monkeypatch.setattr(setup_cmd.store, "set_config", set_config)
    full_tags = [discord.ForumTag(name=f"existing-{i}") for i in range(19)]
    channel = _forum_channel(available_tags=full_tags)
    channel.edit = AsyncMock()
    interaction = _admin_interaction(channel)
    await setup_cmd.handle_setup(MagicMock(), interaction)
    set_config.assert_not_awaited()
    channel.edit.assert_not_awaited()
    message = interaction.followup.send.await_args.args[0]
    assert "room" in message


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


def test_cog_defines_all_beacon_commands():
    from src.commands.beacons import BeaconsCog

    names = {cmd.name for cmd in BeaconsCog.beacon.commands}
    assert {"setup", "role", "mining", "medic", "squad", "backup", "cargo", "salvage"} <= names
