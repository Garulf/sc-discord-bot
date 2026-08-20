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
    assert (
        "700" in interaction.followup.send.await_args.args[0]
        or message.jump_url in interaction.followup.send.await_args.args[0]
    )


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


def _guild(*, member=None, channel=None, thread_channel=None):
    guild = MagicMock()
    guild.id = 1
    guild.get_member = MagicMock(return_value=member)
    guild.fetch_member = AsyncMock(return_value=member)
    guild.get_channel = MagicMock(return_value=channel or thread_channel)
    return guild


def _member(user_id=42, display_name="Nova"):
    member = MagicMock()
    member.id = user_id
    member.display_name = display_name
    return member


@pytest.fixture
def make_maintenance_cog(monkeypatch):
    def _make(*, records=None, config=THREAD_CONFIG, beacon=None, thread=None, create_error=None, get_scheduled=None):
        records = records or []
        cog = MagicMock()
        cog.bot.state = MagicMock()
        monkeypatch.setattr(scheduled.store, "scheduled_beacons", AsyncMock(return_value=records))
        monkeypatch.setattr(scheduled.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(scheduled.store, "save_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "delete_scheduled", AsyncMock())
        monkeypatch.setattr(scheduled.store, "clear_scheduled_open", AsyncMock())
        monkeypatch.setattr(scheduled.store, "get_beacon", AsyncMock(return_value=beacon))
        monkeypatch.setattr(scheduled.store, "save_beacon", AsyncMock())
        if get_scheduled is not None:
            monkeypatch.setattr(scheduled.store, "get_scheduled", get_scheduled)
        else:
            records_by_id = dict(records)
            monkeypatch.setattr(
                scheduled.store,
                "get_scheduled",
                AsyncMock(side_effect=lambda state, message_id: records_by_id.get(message_id)),
            )
        if create_error is not None:
            monkeypatch.setattr(scheduled.lifecycle, "create_beacon_thread", AsyncMock(side_effect=create_error))
        else:
            monkeypatch.setattr(scheduled.lifecycle, "create_beacon_thread", AsyncMock(return_value=thread))
        monkeypatch.setattr(scheduled.lifecycle, "_refresh_board", AsyncMock())
        return cog

    return _make


@pytest.mark.asyncio
async def test_run_scheduled_beacons_sends_reminder_once(make_maintenance_cog):
    channel = MagicMock()
    channel.send = AsyncMock()
    record = _scheduled_record(open_at=1000.0, rsvp=[7, 8], reminded_at=None)
    cog = make_maintenance_cog(records=[(700, record)])
    guild = _guild(channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0 - 500)

    channel.send.assert_awaited_once()
    content = channel.send.await_args.args[0]
    assert "<@7>" in content and "<@8>" in content
    saved = scheduled.store.save_scheduled.await_args.args[2]
    assert saved["reminded_at"] == 1000.0 - 500


@pytest.mark.asyncio
async def test_run_scheduled_beacons_does_not_remind_twice(make_maintenance_cog):
    channel = MagicMock()
    channel.send = AsyncMock()
    record = _scheduled_record(open_at=1000.0, rsvp=[7], reminded_at=1000.0 - 550)
    cog = make_maintenance_cog(records=[(700, record)])
    guild = _guild(channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0 - 500)

    channel.send.assert_not_awaited()
    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_does_not_remind_before_window(make_maintenance_cog):
    record = _scheduled_record(open_at=1000.0, rsvp=[7], reminded_at=None)
    cog = make_maintenance_cog(records=[(700, record)])
    guild = _guild(channel=MagicMock())

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0 - 700)

    scheduled.store.save_scheduled.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_fires_and_auto_joins_rsvp(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    thread = MagicMock()
    thread.id = 900
    thread.add_user = AsyncMock()
    beacon = {
        "members": [],
        "status": "open",
        "last_activity_at": 0.0,
        "first_joined_at": None,
    }
    record = _scheduled_record(open_at=1000.0, rsvp=[7, 8])
    cog = make_maintenance_cog(records=[(700, record)], beacon=beacon, thread=thread)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.lifecycle.create_beacon_thread.assert_awaited_once()
    saved_beacon = scheduled.store.save_beacon.await_args.args[2]
    assert sorted(saved_beacon["members"]) == [7, 8]
    assert saved_beacon["status"] == "active"
    assert thread.add_user.await_count == 2
    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    scheduled.store.clear_scheduled_open.assert_awaited_once()
    message.edit.assert_awaited_once()
    assert message.edit.await_args.kwargs["view"] is None


@pytest.mark.asyncio
async def test_run_scheduled_beacons_aborts_when_config_missing(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    record = _scheduled_record(open_at=1000.0)
    cog = make_maintenance_cog(records=[(700, record)], config=None)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.lifecycle.create_beacon_thread.assert_not_awaited()
    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    message.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_aborts_on_create_failure(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    record = _scheduled_record(open_at=1000.0)
    cog = make_maintenance_cog(
        records=[(700, record)], create_error=discord.HTTPException(MagicMock(status=500), "boom")
    )
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    message.edit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_processes_every_record_in_one_sweep(make_maintenance_cog):
    message = MagicMock()
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    thread = MagicMock()
    thread.id = 900
    thread.add_user = AsyncMock()
    beacon = {"members": [], "status": "open", "last_activity_at": 0.0, "first_joined_at": None}
    first_record = _scheduled_record(open_at=1000.0, rsvp=[])
    second_record = _scheduled_record(open_at=1000.0, rsvp=[])
    cog = make_maintenance_cog(records=[(700, first_record), (701, second_record)], beacon=beacon, thread=thread)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    assert scheduled.lifecycle.create_beacon_thread.await_count == 2
    scheduled.store.delete_scheduled.assert_any_await(cog.bot.state, 700)
    scheduled.store.delete_scheduled.assert_any_await(cog.bot.state, 701)


@pytest.mark.asyncio
async def test_run_scheduled_beacons_rereads_record_under_lock(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    thread = MagicMock()
    thread.id = 900
    thread.add_user = AsyncMock()
    beacon = {"members": [], "status": "open", "last_activity_at": 0.0, "first_joined_at": None}
    stale_record = _scheduled_record(open_at=1000.0, rsvp=[])
    cog = make_maintenance_cog(records=[(700, stale_record)], beacon=beacon, thread=thread)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.store.get_scheduled.assert_any_await(cog.bot.state, 700)


@pytest.mark.asyncio
async def test_run_scheduled_beacons_skips_fire_when_concurrently_cancelled(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    record = _scheduled_record(open_at=1000.0)
    cog = make_maintenance_cog(records=[(700, record)], get_scheduled=AsyncMock(return_value=None))
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.lifecycle.create_beacon_thread.assert_not_awaited()
    scheduled.store.delete_scheduled.assert_not_awaited()
    scheduled.lifecycle._refresh_board.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_refreshes_board_on_fire(make_maintenance_cog):
    message = MagicMock()
    message.id = 700
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    thread = MagicMock()
    thread.id = 900
    thread.add_user = AsyncMock()
    beacon = {"members": [], "status": "open", "last_activity_at": 0.0, "first_joined_at": None}
    record = _scheduled_record(open_at=1000.0, rsvp=[])
    cog = make_maintenance_cog(records=[(700, record)], beacon=beacon, thread=thread)
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.lifecycle._refresh_board.assert_awaited_once_with(cog, guild)


@pytest.mark.asyncio
async def test_run_scheduled_beacons_does_not_refresh_board_on_reminder(make_maintenance_cog):
    channel = MagicMock()
    channel.send = AsyncMock()
    record = _scheduled_record(open_at=1000.0, rsvp=[7], reminded_at=None)
    cog = make_maintenance_cog(records=[(700, record)])
    guild = _guild(channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0 - 500)

    scheduled.lifecycle._refresh_board.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_scheduled_beacons_one_failure_does_not_block_others(make_maintenance_cog):
    message = MagicMock()
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    beacon = {"members": [], "status": "open", "last_activity_at": 0.0, "first_joined_at": None}
    ok_record = _scheduled_record(open_at=1000.0, rsvp=[])
    cog = make_maintenance_cog(
        records=[(700, ok_record)],
        beacon=beacon,
        create_error=discord.HTTPException(MagicMock(status=500), "boom"),
    )
    guild = _guild(member=_member(), channel=channel)

    await scheduled.run_scheduled_beacons(cog, guild, now=1000.0)

    scheduled.store.delete_scheduled.assert_awaited_once_with(cog.bot.state, 700)
    message.edit.assert_awaited_once()
