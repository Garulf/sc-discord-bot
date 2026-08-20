import time
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import scheduled

THREAD_CONFIG = {"channel_id": 10, "mode": "thread", "panel_message_id": 11, "tag_ids": {}, "roles": {}}


def _role(role_id):
    role = MagicMock()
    role.id = role_id
    role.mention = f"<@&{role_id}>"
    return role


def _interaction(guild_id=1, user_id=42, admin=False, roles=()):
    interaction = MagicMock()
    interaction.guild.id = guild_id
    interaction.user.id = user_id
    interaction.user.display_name = "Garulf"
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = list(roles)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.fixture
def make_cog(monkeypatch):
    def _make(config=None, scheduled_open=None, scheduled_record=None):
        cog = MagicMock()
        cog.bot.state = MagicMock()
        cog.scheduled_beacon_view = MagicMock()
        monkeypatch.setattr(scheduled.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(scheduled.store, "get_scheduled_open", AsyncMock(return_value=scheduled_open))
        monkeypatch.setattr(scheduled.store, "set_scheduled_open", AsyncMock())
        monkeypatch.setattr(scheduled.store, "save_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "get_scheduled", AsyncMock(return_value=scheduled_record))
        monkeypatch.setattr(scheduled.store, "delete_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "clear_scheduled_open", AsyncMock())
        monkeypatch.setattr(scheduled.lifecycle, "open_beacon", AsyncMock())
        return cog

    return _make


def _config_with_role(role_id):
    return {**THREAD_CONFIG, "settings": {"schedule_role_id": role_id}}


def test_can_schedule_open_when_no_role_configured():
    assert scheduled.can_schedule(_interaction(), THREAD_CONFIG) is True


def test_can_schedule_denies_without_matching_role():
    interaction = _interaction(roles=[_role(9)])
    assert scheduled.can_schedule(interaction, _config_with_role(5)) is False


def test_can_schedule_allows_matching_role():
    interaction = _interaction(roles=[_role(5)])
    assert scheduled.can_schedule(interaction, _config_with_role(5)) is True


def test_can_schedule_allows_admin_regardless_of_role():
    interaction = _interaction(admin=True)
    assert scheduled.can_schedule(interaction, _config_with_role(5)) is True


def test_can_schedule_allows_sc_bot_role_regardless_of_gate():
    sc_bot_role = MagicMock()
    sc_bot_role.id = 12345
    sc_bot_role.name = "sc-bot"
    interaction = _interaction(roles=[sc_bot_role])
    assert scheduled.can_schedule(interaction, _config_with_role(5)) is True


@pytest.mark.asyncio
async def test_schedule_rejects_malformed_location(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "a:b:c:d"}, 3600)
    assert "system:planet:location" in interaction.followup.send.await_args.args[0]
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_requires_setup(make_cog):
    cog = make_cog(config=None)
    interaction = _interaction()
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)
    assert "setup" in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
async def test_schedule_rejects_when_role_gated_and_missing_role(make_cog):
    cog = make_cog(config=_config_with_role(5))
    interaction = _interaction(roles=[_role(9)])
    interaction.guild.get_role = MagicMock(return_value=_role(5))
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)
    msg = interaction.followup.send.await_args.args[0]
    assert "<@&5>" in msg
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_rejects_duplicate_pending(make_cog):
    cog = make_cog(config=THREAD_CONFIG, scheduled_open=555)
    interaction = _interaction()
    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)
    assert "already have a pending" in interaction.followup.send.await_args.args[0]
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_schedule_posts_embed_and_saves_state(make_cog):
    cog = make_cog(config=THREAD_CONFIG)
    interaction = _interaction()
    message = MagicMock()
    message.id = 700
    message.jump_url = "https://discord.com/channels/1/10/700"
    channel = MagicMock()
    channel.send = AsyncMock(return_value=message)
    interaction.guild.get_channel = MagicMock(return_value=channel)
    before = time.time()

    await scheduled.schedule_beacon(cog, interaction, "medic", {"location": "Stanton"}, 3600)

    channel.send.assert_awaited_once()
    assert channel.send.await_args.kwargs["view"] is cog.scheduled_beacon_view
    scheduled.store.save_scheduled.assert_awaited_once()
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["requester_id"] == 42
    assert saved["rsvp"] == []
    assert saved["open_at"] >= before + 3600
    scheduled.store.set_scheduled_open.assert_awaited_once_with(cog.bot.state, 1, 42, "medic", 700)
    assert "700" in interaction.followup.send.await_args.args[0] or message.jump_url in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
async def test_open_or_schedule_calls_open_beacon_when_when_is_none(make_cog):
    cog = make_cog()
    interaction = _interaction()
    await scheduled.open_or_schedule(cog, interaction, "medic", {"location": "Stanton"}, None)
    scheduled.lifecycle.open_beacon.assert_awaited_once_with(cog, interaction, "medic", {"location": "Stanton"})


@pytest.mark.asyncio
async def test_open_or_schedule_rejects_invalid_duration(make_cog):
    cog = make_cog()
    interaction = _interaction()
    await scheduled.open_or_schedule(cog, interaction, "medic", {"location": "Stanton"}, "soon")
    interaction.response.send_message.assert_awaited_once()
    msg = interaction.response.send_message.await_args.args[0]
    assert "soon" in msg
    scheduled.lifecycle.open_beacon.assert_not_awaited()


def _scheduled_record(**overrides):
    record = {
        "guild_id": 1,
        "channel_id": 10,
        "category": "medic",
        "requester_id": 42,
        "fields": {"location": "Stanton"},
        "open_at": 99999.0,
        "rsvp": [],
        "reminded_at": None,
        "created_at": 100.0,
    }
    record.update(overrides)
    return record


def _button_interaction(user_id=42, admin=False):
    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.user.id = user_id
    interaction.user.guild_permissions.administrator = admin
    interaction.user.roles = []
    interaction.message.id = 700
    interaction.message.edit = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_handle_scheduled_join_adds_rsvp(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record())
    interaction = _button_interaction(user_id=7)
    await scheduled.handle_scheduled_join(cog, interaction)
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["rsvp"] == [7]
    interaction.message.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_scheduled_join_rejects_duplicate(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record(rsvp=[7]))
    interaction = _button_interaction(user_id=7)
    await scheduled.handle_scheduled_join(cog, interaction)
    assert "already" in interaction.followup.send.await_args.args[0]
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_scheduled_leave_removes_rsvp(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record(rsvp=[7]))
    interaction = _button_interaction(user_id=7)
    await scheduled.handle_scheduled_leave(cog, interaction)
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["rsvp"] == []


@pytest.mark.asyncio
async def test_handle_scheduled_cancel_requires_requester_or_admin(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record())
    interaction = _button_interaction(user_id=999)
    await scheduled.handle_scheduled_cancel(cog, interaction)
    assert "Only the requester" in interaction.followup.send.await_args.args[0]
    scheduled.store.delete_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_scheduled_cancel_deletes_record_for_requester(make_cog):
    cog = make_cog(scheduled_record=_scheduled_record())
    interaction = _button_interaction(user_id=42)
    await scheduled.handle_scheduled_cancel(cog, interaction)
    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    scheduled.store.clear_scheduled_open.assert_awaited_once_with(cog.bot.state, 1, 42, "medic")
    interaction.message.edit.assert_awaited_once()
