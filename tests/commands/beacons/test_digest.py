from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.beacons import digest
from src.commands.beacons.rules import STATUS_CLOSED, STATUS_OPEN

WEEK = digest.WEEK_SECONDS


def _beacon(**overrides):
    beacon = {
        "guild_id": 1,
        "category": "mining",
        "requester_id": 100,
        "members": [],
        "status": STATUS_OPEN,
        "opened_at": 1000.0,
        "first_joined_at": None,
        "closed_at": None,
    }
    beacon.update(overrides)
    return beacon


@pytest.fixture
def make_cog(monkeypatch):
    def _make(config=None, beacons=None, reps=None):
        cog = MagicMock()
        cog.bot.state = MagicMock()
        monkeypatch.setattr(digest.store, "get_config", AsyncMock(return_value=config))
        monkeypatch.setattr(digest.store, "set_config", AsyncMock())
        monkeypatch.setattr(digest.store, "all_beacons", AsyncMock(return_value=beacons or []))
        monkeypatch.setattr(digest.store, "get_reps", AsyncMock(return_value=reps or {}))
        return cog

    return _make


def _guild(channel=None):
    guild = MagicMock()
    guild.id = 1
    guild.get_channel = MagicMock(return_value=channel)
    return guild


@pytest.mark.asyncio
async def test_unset_digest_channel_never_posts(make_cog):
    cog = make_cog(config={"settings": {}})
    guild = _guild(channel=MagicMock())
    await digest.maybe_post_digest(cog, guild, now=1_000_000.0)
    guild.get_channel.assert_not_called()
    digest.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_not_yet_due_returns_without_posting(make_cog):
    now = 1_000_000.0
    config = {"settings": {"digest_channel_id": 55}, "last_digest_at": now - WEEK + 10}
    cog = make_cog(config=config)
    channel = MagicMock()
    channel.send = AsyncMock()
    guild = _guild(channel=channel)
    await digest.maybe_post_digest(cog, guild, now=now)
    channel.send.assert_not_awaited()
    digest.store.set_config.assert_not_awaited()


@pytest.mark.asyncio
async def test_due_posts_and_stamps_last_digest_at(make_cog):
    now = 1_000_000.0
    config = {"settings": {"digest_channel_id": 55}, "last_digest_at": now - WEEK - 10}
    beacons = [(1, _beacon(opened_at=now - 100))]
    cog = make_cog(config=config, beacons=beacons)
    channel = MagicMock()
    channel.send = AsyncMock()
    guild = _guild(channel=channel)
    await digest.maybe_post_digest(cog, guild, now=now)
    channel.send.assert_awaited_once()
    _, kwargs = channel.send.await_args
    assert "embed" in kwargs
    saved_config = digest.store.set_config.await_args.args[2]
    assert saved_config["last_digest_at"] == now


@pytest.mark.asyncio
async def test_never_posted_before_posts_immediately(make_cog):
    now = 1_000_000.0
    config = {"settings": {"digest_channel_id": 55}}
    beacons = [(1, _beacon(opened_at=now - 100))]
    cog = make_cog(config=config, beacons=beacons)
    channel = MagicMock()
    channel.send = AsyncMock()
    guild = _guild(channel=channel)
    await digest.maybe_post_digest(cog, guild, now=now)
    channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_weekly_slice_excludes_old_beacons(make_cog):
    now = 1_000_000.0
    config = {"settings": {"digest_channel_id": 55}, "last_digest_at": now - WEEK - 10}
    old_beacon = _beacon(opened_at=now - WEEK - 1000, status=STATUS_CLOSED)
    recent_beacon = _beacon(opened_at=now - 100)
    beacons = [(1, old_beacon), (2, recent_beacon)]
    cog = make_cog(config=config, beacons=beacons)
    channel = MagicMock()
    channel.send = AsyncMock()
    guild = _guild(channel=channel)
    await digest.maybe_post_digest(cog, guild, now=now)
    embed = channel.send.await_args.kwargs["embed"]
    overview = next(field for field in embed.fields if field.name == "Overview")
    assert "Opened: 1" in overview.value


@pytest.mark.asyncio
async def test_missing_channel_stamps_last_digest_at_without_posting(make_cog):
    now = 1_000_000.0
    config = {"settings": {"digest_channel_id": 55}, "last_digest_at": now - WEEK - 10}
    cog = make_cog(config=config, beacons=[(1, _beacon(opened_at=now - 100))])
    guild = _guild(channel=None)
    await digest.maybe_post_digest(cog, guild, now=now)
    saved_config = digest.store.set_config.await_args.args[2]
    assert saved_config["last_digest_at"] == now


def test_build_digest_embed_contains_counts_and_leaderboards():
    computed = {
        "total": 3,
        "open": 1,
        "closed": 2,
        "by_category": {"mining": 2, "medic": 1},
        "top_responders": [(10, 2)],
        "top_commended": [(5, 3)],
        "avg_first_join_seconds": None,
    }
    embed = digest.build_digest_embed(computed, since=0.0)
    assert embed.title == "Weekly Beacon Digest"
    text = " ".join(str(field.value) for field in embed.fields)
    assert "Opened: 3" in text
    assert "Closed: 2" in text
    assert "Mining" in text
    assert "<@10>" in text
