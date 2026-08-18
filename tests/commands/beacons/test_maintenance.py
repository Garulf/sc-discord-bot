from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.commands.beacons import maintenance
from src.commands.beacons.rules import STATUS_ACTIVE, STATUS_CLOSED, STATUS_OPEN

SETTINGS_CONFIG = {
    "roles": {},
    "settings": {
        "idle_warn_minutes": 120,
        "idle_close_minutes": 60,
        "escalate_minutes": 15,
    },
}


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


@pytest.fixture
def make_cog(monkeypatch):
    def _make(config=None, beacons=None):
        beacons = beacons or []
        by_id = dict(beacons)
        cog = MagicMock()
        cog.bot.state = MagicMock()
        monkeypatch.setattr(maintenance.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(maintenance.store, "open_beacons", AsyncMock(return_value=beacons))
        monkeypatch.setattr(maintenance.store, "get_beacon", AsyncMock(side_effect=lambda state, tid: by_id.get(tid)))
        monkeypatch.setattr(maintenance.store, "save_beacon", AsyncMock())
        monkeypatch.setattr(maintenance.store, "clear_open_beacon", AsyncMock())
        return cog

    return _make


def _guild(thread):
    guild = MagicMock()
    guild.id = 1
    guild.get_thread = MagicMock(return_value=thread)
    guild.get_channel = MagicMock(return_value=None)
    return guild


def _thread(thread_id=99):
    thread = MagicMock()
    thread.id = thread_id
    thread.send = AsyncMock()
    return thread


@pytest.mark.asyncio
async def test_fresh_beacon_does_nothing(make_cog):
    beacon = _beacon(opened_at=1000.0, last_activity_at=1000.0)
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    await maintenance.run_maintenance(cog, guild, now=1000.0)
    thread.send.assert_not_called()
    maintenance.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_escalation_fires_once_and_only_once(make_cog):
    beacon = _beacon(opened_at=0.0, last_activity_at=0.0)
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    now = 15 * 60
    await maintenance.run_maintenance(cog, guild, now=now)
    thread.send.assert_awaited_once()
    assert "no responders" in thread.send.await_args.args[0]
    saved = maintenance.store.save_beacon.await_args.args[2]
    assert saved["escalated_at"] == now

    thread.send.reset_mock()
    maintenance.store.save_beacon.reset_mock()
    beacon2 = _beacon(opened_at=0.0, last_activity_at=0.0, escalated_at=now)
    cog2 = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon2)])
    await maintenance.run_maintenance(cog2, guild, now=now + 60)
    thread.send.assert_not_called()


@pytest.mark.asyncio
async def test_escalation_pings_mapped_role(make_cog):
    config = {
        "roles": {"medic": 5},
        "settings": SETTINGS_CONFIG["settings"],
    }
    beacon = _beacon(opened_at=0.0, last_activity_at=0.0)
    cog = make_cog(config=config, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    await maintenance.run_maintenance(cog, guild, now=15 * 60)
    assert thread.send.await_args.args[0] == "<@&5> this beacon has had no responders yet."


@pytest.mark.asyncio
async def test_idle_warn_fires_after_idle_window(make_cog):
    beacon = _beacon(
        opened_at=0.0,
        last_activity_at=0.0,
        escalated_at=0.0,
        status=STATUS_ACTIVE,
        members=[2],
    )
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    now = 120 * 60
    await maintenance.run_maintenance(cog, guild, now=now)
    thread.send.assert_awaited_once()
    assert "<@1>" in thread.send.await_args.args[0]
    assert "closes automatically in 60 minutes" in thread.send.await_args.args[0]
    saved = maintenance.store.save_beacon.await_args.args[2]
    assert saved["warned_at"] == now


@pytest.mark.asyncio
async def test_activity_after_warn_resets_warned_at(make_cog):
    beacon = _beacon(
        opened_at=0.0,
        last_activity_at=200.0,
        escalated_at=0.0,
        warned_at=100.0,
        status=STATUS_ACTIVE,
        members=[2],
    )
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    await maintenance.run_maintenance(cog, guild, now=300.0)
    saved = maintenance.store.save_beacon.await_args.args[2]
    assert saved["warned_at"] is None


@pytest.mark.asyncio
async def test_auto_close_invoked_after_warn_and_timeout(make_cog, monkeypatch):
    close_beacon = AsyncMock()
    monkeypatch.setattr(maintenance, "close_beacon", close_beacon)
    beacon = _beacon(
        opened_at=0.0,
        last_activity_at=100.0,
        escalated_at=0.0,
        warned_at=100.0,
        status=STATUS_ACTIVE,
        members=[2],
    )
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    now = 100.0 + 60 * 60
    await maintenance.run_maintenance(cog, guild, now=now)
    close_beacon.assert_awaited_once_with(cog, thread, beacon, None)


@pytest.mark.asyncio
async def test_closed_beacon_from_re_read_is_skipped(make_cog):
    beacon = _beacon(opened_at=0.0, last_activity_at=0.0, status=STATUS_CLOSED)
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    await maintenance.run_maintenance(cog, guild, now=15 * 60)
    thread.send.assert_not_called()
    maintenance.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_beacon_removed_before_lock_is_skipped(make_cog, monkeypatch):
    beacon = _beacon(opened_at=0.0, last_activity_at=0.0)
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    monkeypatch.setattr(maintenance.store, "get_beacon", AsyncMock(return_value=None))
    thread = _thread()
    guild = _guild(thread)
    await maintenance.run_maintenance(cog, guild, now=15 * 60)
    thread.send.assert_not_called()
    maintenance.store.save_beacon.assert_not_awaited()


@pytest.mark.asyncio
async def test_thread_resolution_falls_back_to_fetch_channel(make_cog):
    beacon = _beacon(opened_at=0.0, last_activity_at=0.0)
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = MagicMock()
    guild.id = 1
    guild.get_thread = MagicMock(return_value=None)
    guild.get_channel = MagicMock(return_value=None)
    guild.fetch_channel = AsyncMock(return_value=thread)
    await maintenance.run_maintenance(cog, guild, now=15 * 60)
    guild.fetch_channel.assert_awaited_once_with(99)
    thread.send.assert_awaited_once()
    maintenance.store.save_beacon.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_closed_and_index_cleared_when_fetch_raises_not_found(make_cog):
    beacon = _beacon(opened_at=0.0, last_activity_at=0.0, guild_id=7, requester_id=3, category="medic")
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    guild = MagicMock()
    guild.id = 1
    guild.get_thread = MagicMock(return_value=None)
    guild.get_channel = MagicMock(return_value=None)
    guild.fetch_channel = AsyncMock(side_effect=discord.NotFound(MagicMock(status=404), "Unknown Channel"))
    await maintenance.run_maintenance(cog, guild, now=999.0)
    saved = maintenance.store.save_beacon.await_args.args[2]
    assert saved["status"] == STATUS_CLOSED
    assert saved["closed_at"] == 999.0
    assert saved["closed_by_id"] is None
    maintenance.store.clear_open_beacon.assert_awaited_once_with(cog.bot.state, 7, 3, "medic")


@pytest.mark.asyncio
async def test_run_maintenance_reuses_sweep_entries_for_board_refresh(make_cog, monkeypatch):
    beacon = _beacon(opened_at=1000.0, last_activity_at=1000.0)
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(99, beacon)])
    thread = _thread()
    guild = _guild(thread)
    refresh = AsyncMock()
    monkeypatch.setattr(maintenance.board, "refresh_board", refresh)
    await maintenance.run_maintenance(cog, guild, now=1000.0)
    refresh.assert_awaited_once_with(cog, guild, entries=[(99, beacon)])


@pytest.mark.asyncio
async def test_beacon_failure_does_not_stop_sweep(make_cog, monkeypatch):
    beacon_ok = _beacon(opened_at=0.0, last_activity_at=0.0)
    beacon_bad = _beacon(opened_at=0.0, last_activity_at=0.0)
    cog = make_cog(config=SETTINGS_CONFIG, beacons=[(1, beacon_bad), (2, beacon_ok)])
    thread_bad = _thread(thread_id=1)
    thread_bad.send = AsyncMock(side_effect=Exception("boom"))
    thread_ok = _thread(thread_id=2)
    guild = MagicMock()
    guild.id = 1
    guild.get_thread = MagicMock(side_effect=lambda tid: thread_bad if tid == 1 else thread_ok)
    guild.get_channel = MagicMock(return_value=None)
    await maintenance.run_maintenance(cog, guild, now=15 * 60)
    thread_ok.send.assert_awaited_once()
