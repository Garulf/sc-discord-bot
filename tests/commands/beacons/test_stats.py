from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.beacons import stats
from src.commands.beacons.rules import STATUS_CLOSED, STATUS_OPEN


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


def test_compute_stats_counts_total_open_closed():
    beacons = [
        (1, _beacon(status=STATUS_OPEN)),
        (2, _beacon(status=STATUS_CLOSED)),
        (3, _beacon(status=STATUS_CLOSED)),
    ]
    result = stats.compute_stats(beacons, {})
    assert result["total"] == 3
    assert result["open"] == 1
    assert result["closed"] == 2


def test_compute_stats_by_category_counts_all_regardless_of_status():
    beacons = [
        (1, _beacon(category="mining", status=STATUS_OPEN)),
        (2, _beacon(category="mining", status=STATUS_CLOSED)),
        (3, _beacon(category="medic", status=STATUS_CLOSED)),
    ]
    result = stats.compute_stats(beacons, {})
    assert result["by_category"] == {"mining": 2, "medic": 1}


def test_compute_stats_top_responders_sorted_by_count_desc_then_user_id_asc():
    beacons = [
        (1, _beacon(members=[10, 20])),
        (2, _beacon(members=[10])),
        (3, _beacon(members=[30])),
        (4, _beacon(members=[20])),
    ]
    result = stats.compute_stats(beacons, {})
    assert result["top_responders"] == [(10, 2), (20, 2), (30, 1)]


def test_compute_stats_top_responders_caps_at_five():
    beacons = [(i, _beacon(members=[i])) for i in range(10)]
    result = stats.compute_stats(beacons, {})
    assert len(result["top_responders"]) == 5


def test_compute_stats_top_commended_from_reps_sorted_desc_then_user_id_asc():
    reps = {5: 3, 6: 3, 7: 1}
    result = stats.compute_stats([], reps)
    assert result["top_commended"] == [(5, 3), (6, 3), (7, 1)]


def test_compute_stats_top_commended_caps_at_five():
    reps = {i: 1 for i in range(10)}
    result = stats.compute_stats([], reps)
    assert len(result["top_commended"]) == 5


def test_compute_stats_avg_first_join_seconds_none_when_no_data():
    beacons = [(1, _beacon(first_joined_at=None))]
    result = stats.compute_stats(beacons, {})
    assert result["avg_first_join_seconds"] is None


def test_compute_stats_avg_first_join_seconds_computed_over_beacons_with_first_join():
    beacons = [
        (1, _beacon(opened_at=0.0, first_joined_at=60.0)),
        (2, _beacon(opened_at=0.0, first_joined_at=120.0)),
        (3, _beacon(opened_at=0.0, first_joined_at=None)),
    ]
    result = stats.compute_stats(beacons, {})
    assert result["avg_first_join_seconds"] == 90.0


def test_compute_stats_empty_beacons_and_reps():
    result = stats.compute_stats([], {})
    assert result["total"] == 0
    assert result["open"] == 0
    assert result["closed"] == 0
    assert result["by_category"] == {}
    assert result["top_responders"] == []
    assert result["top_commended"] == []
    assert result["avg_first_join_seconds"] is None


def test_build_stats_embed_contains_mentions_and_category_labels():
    computed = {
        "total": 3,
        "open": 1,
        "closed": 2,
        "by_category": {"mining": 2, "medic": 1},
        "top_responders": [(10, 2), (20, 1)],
        "top_commended": [(5, 3)],
        "avg_first_join_seconds": 90.0,
    }
    embed = stats.build_stats_embed(computed)
    text = " ".join(str(field.value) for field in embed.fields) + " " + (embed.description or "")
    assert "<@10>" in text
    assert "<@20>" in text
    assert "<@5>" in text
    assert "Mining" in text
    assert "Medical" in text
    assert "1.5" in text


def test_build_stats_embed_shows_na_when_no_avg():
    computed = {
        "total": 0,
        "open": 0,
        "closed": 0,
        "by_category": {},
        "top_responders": [],
        "top_commended": [],
        "avg_first_join_seconds": None,
    }
    embed = stats.build_stats_embed(computed)
    text = " ".join(str(field.value) for field in embed.fields) + " " + (embed.description or "")
    assert "n/a" in text


@pytest.mark.asyncio
async def test_stats_command_defers_non_ephemeral_and_replies_via_followup(monkeypatch):
    monkeypatch.setattr(stats.store, "all_beacons", AsyncMock(return_value=[]))
    monkeypatch.setattr(stats.store, "get_reps", AsyncMock(return_value={}))

    cog = MagicMock()
    cog.bot.state = MagicMock()

    interaction = MagicMock()
    interaction.guild.id = 1
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    await stats.handle_stats(cog, interaction)

    interaction.response.defer.assert_awaited_once_with()
    interaction.followup.send.assert_awaited_once()
    _, kwargs = interaction.followup.send.await_args
    assert "embed" in kwargs
