from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import setup_cmd


def _cog():
    cog = MagicMock()
    cog.refresh_command_mentions = AsyncMock()
    cog.command_mention = MagicMock(side_effect=lambda key: f"</beacon {key}:1>")
    return cog


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
    cog = _cog()
    interaction = _admin_interaction(channel)
    await setup_cmd.handle_setup(cog, interaction)
    channel.send.assert_awaited_once()
    sent = channel.send.await_args
    assert "</beacon mining:1>" in sent.args[0]
    assert "view" not in sent.kwargs and "embed" not in sent.kwargs
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
    interaction = _admin_interaction(channel)
    interaction.guild.get_channel = MagicMock(return_value=None)
    await setup_cmd.handle_setup(_cog(), interaction)
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
    await setup_cmd.handle_setup(_cog(), interaction)
    assert saved["mode"] == "forum"
    assert saved["channel_id"] == 20
    assert saved["panel_message_id"] == 55
    expected_keys = {
        "mining",
        "medic",
        "squad",
        "backup",
        "cargo",
        "salvage",
        "escort",
        "transport",
        "contested",
        "open",
        "closed",
    }
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
    await setup_cmd.handle_setup(_cog(), interaction)
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
    await setup_cmd.handle_setup(_cog(), interaction, other_channel)
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
    await setup_cmd.handle_setup(_cog(), interaction)
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
    from src.commands.beacons.categories import CATEGORIES

    names = {cmd.name for cmd in BeaconsCog.beacon.commands}
    assert {"setup", "role"} | set(CATEGORIES) <= names


@pytest.mark.asyncio
async def test_config_requires_setup(monkeypatch):
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=None))
    interaction = _admin_interaction(MagicMock())
    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        digest_channel=None,
        clear_digest=None,
    )
    assert "setup" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_config_with_no_options_reports_effective_settings(monkeypatch):
    config = {"channel_id": 1, "mode": "thread", "panel_message_id": 2, "tag_ids": {}, "roles": {}}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    set_config = AsyncMock()
    monkeypatch.setattr(setup_cmd.store, "set_config", set_config)
    interaction = _admin_interaction(MagicMock())
    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        digest_channel=None,
        clear_digest=None,
    )
    set_config.assert_awaited_once()
    message = interaction.response.send_message.await_args.args[0]
    assert "120" in message
    assert "60" in message
    assert "15" in message


@pytest.mark.asyncio
async def test_config_merges_provided_values(monkeypatch):
    config = {
        "channel_id": 1,
        "mode": "thread",
        "panel_message_id": 2,
        "tag_ids": {},
        "roles": {},
        "settings": {"idle_warn_minutes": 200},
    }
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    interaction = _admin_interaction(MagicMock())
    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=30,
        escalate=None,
        voice=True,
        digest_channel=None,
        clear_digest=None,
    )
    assert saved["settings"]["idle_warn_minutes"] == 200
    assert saved["settings"]["idle_close_minutes"] == 30
    assert saved["settings"]["voice"] is True


@pytest.mark.asyncio
async def test_config_sets_voice_category(monkeypatch):
    config = {"channel_id": 1, "mode": "thread", "panel_message_id": 2, "tag_ids": {}, "roles": {}}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    interaction = _admin_interaction(MagicMock())
    category = MagicMock()
    category.id = 900
    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        voice_category=category,
        digest_channel=None,
        clear_digest=None,
    )
    assert saved["settings"]["voice_category_id"] == 900
    assert "<#900>" in interaction.response.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_config_sets_digest_channel(monkeypatch):
    config = {"channel_id": 1, "mode": "thread", "panel_message_id": 2, "tag_ids": {}, "roles": {}}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    interaction = _admin_interaction(MagicMock())
    digest_channel = MagicMock()
    digest_channel.id = 555
    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        digest_channel=digest_channel,
        clear_digest=None,
    )
    assert saved["settings"]["digest_channel_id"] == 555


@pytest.mark.asyncio
async def test_config_clear_digest_wins_over_digest_channel(monkeypatch):
    config = {
        "channel_id": 1,
        "mode": "thread",
        "panel_message_id": 2,
        "tag_ids": {},
        "roles": {},
        "settings": {"digest_channel_id": 111},
    }
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=config))
    saved = {}
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    interaction = _admin_interaction(MagicMock())
    digest_channel = MagicMock()
    digest_channel.id = 555
    await setup_cmd.handle_config(
        MagicMock(),
        interaction,
        idle_warn=None,
        idle_close=None,
        escalate=None,
        voice=None,
        digest_channel=digest_channel,
        clear_digest=True,
    )
    assert saved["settings"]["digest_channel_id"] is None


@pytest.mark.asyncio
async def test_resetup_deletes_previous_panel_message(monkeypatch):
    saved = {}
    old = {"channel_id": 9, "mode": "thread", "panel_message_id": 33, "tag_ids": {}, "roles": {}}
    monkeypatch.setattr(setup_cmd.store, "get_config", AsyncMock(return_value=old))
    monkeypatch.setattr(setup_cmd.store, "set_config", AsyncMock(side_effect=lambda s, g, c: saved.update(c)))
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 10
    message = MagicMock()
    message.id = 11
    channel.send = AsyncMock(return_value=message)
    old_channel = MagicMock(spec=discord.TextChannel)
    old_message = MagicMock()
    old_message.delete = AsyncMock()
    old_channel.get_partial_message = MagicMock(return_value=old_message)
    interaction = _admin_interaction(channel)
    interaction.guild.get_channel = MagicMock(return_value=old_channel)
    await setup_cmd.handle_setup(_cog(), interaction)
    old_message.delete.assert_awaited_once()
    assert saved["panel_message_id"] == 11
