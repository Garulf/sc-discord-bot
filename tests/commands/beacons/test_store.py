import pytest

from src.commands.beacons import store
from src.storage import Database, StateStore


@pytest.fixture
async def state(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    await db.connect()
    yield StateStore(db)
    await db.close()


@pytest.mark.asyncio
async def test_config_roundtrip(state):
    assert await store.get_config(state, 1) is None
    config = {"channel_id": 10, "mode": "thread", "panel_message_id": 11, "tag_ids": {}, "roles": {"medic": 5}}
    await store.set_config(state, 1, config)
    assert await store.get_config(state, 1) == config


@pytest.mark.asyncio
async def test_beacon_roundtrip(state):
    assert await store.get_beacon(state, 99) is None
    beacon = {
        "guild_id": 1,
        "category": "medic",
        "requester_id": 42,
        "members": [],
        "status": "open",
        "opened_at": 123.0,
        "closed_at": None,
        "closed_by_id": None,
        "fields": {"location": "Stanton:Hurston:Lorville"},
    }
    await store.save_beacon(state, 99, beacon)
    stored = await store.get_beacon(state, 99)
    assert stored.items() >= beacon.items()


@pytest.mark.asyncio
async def test_open_beacon_index(state):
    assert await store.get_open_beacon(state, 1, 42, "medic") is None
    await store.set_open_beacon(state, 1, 42, "medic", 99)
    assert await store.get_open_beacon(state, 1, 42, "medic") == 99
    assert await store.get_open_beacon(state, 1, 42, "mining") is None
    await store.clear_open_beacon(state, 1, 42, "medic")
    assert await store.get_open_beacon(state, 1, 42, "medic") is None


@pytest.mark.asyncio
async def test_migrate_legacy_keys_copies_ticket_state(state):
    await state.set("tickets:config:1", {"channel_id": 10})
    await state.set("tickets:ticket:99", {"category": "medic", "status": "open", "requester_id": 1})
    await state.set("tickets:open:1:42:medic", 99)
    await state.set("inventory_subscriptions:1", {"left": "alone"})
    await store.migrate_legacy_keys(state)
    assert await store.get_config(state, 1) == {"channel_id": 10}
    migrated = await store.get_beacon(state, 99)
    assert migrated["category"] == "medic"
    assert migrated["members"] == []
    assert await store.get_open_beacon(state, 1, 42, "medic") == 99
    assert await state.get("tickets:config:1") == {"channel_id": 10}
    assert await state.get("inventory_subscriptions:1") == {"left": "alone"}


@pytest.mark.asyncio
async def test_migrate_legacy_keys_never_overwrites_newer_beacon_state(state):
    await state.set("tickets:config:1", {"channel_id": 10})
    await state.set("beacons:config:1", {"channel_id": 99})
    await store.migrate_legacy_keys(state)
    assert await store.get_config(state, 1) == {"channel_id": 99}


@pytest.mark.asyncio
async def test_get_beacon_normalizes_legacy_claimed_records(state):
    await store.save_beacon(state, 5, {"requester_id": 1, "claimer_id": 7, "status": "claimed"})
    beacon = await store.get_beacon(state, 5)
    assert beacon["status"] == "active"
    assert beacon["members"] == [7]


@pytest.mark.asyncio
async def test_open_beacons_filters_guild_and_status(state):
    await store.save_beacon(
        state, 1, {"guild_id": 10, "status": "open", "requester_id": 1, "members": [], "opened_at": 1.0}
    )
    await store.save_beacon(
        state, 2, {"guild_id": 10, "status": "closed", "requester_id": 1, "members": [], "opened_at": 1.0}
    )
    await store.save_beacon(
        state, 3, {"guild_id": 99, "status": "open", "requester_id": 1, "members": [], "opened_at": 1.0}
    )
    result = await store.open_beacons(state, 10)
    assert [tid for tid, _ in result] == [1]
    everything = await store.all_beacons(state, 10)
    assert sorted(tid for tid, _ in everything) == [1, 2]


@pytest.mark.asyncio
async def test_rep_roundtrip(state):
    assert await store.add_rep(state, 10, 42) == 1
    assert await store.add_rep(state, 10, 42) == 2
    await store.add_rep(state, 10, 7)
    assert await store.get_reps(state, 10) == {42: 2, 7: 1}


@pytest.mark.asyncio
async def test_get_reps_treats_key_deleted_after_listing_as_zero(state):
    await store.add_rep(state, 10, 42)
    await state.set("beacons:rep:10:7", None)
    reps = await store.get_reps(state, 10)
    assert reps == {42: 1, 7: 0}


@pytest.mark.asyncio
async def test_last_open_roundtrip(state):
    assert await store.get_last_open(state, 10, 42) is None
    await store.set_last_open(state, 10, 42, "medic", {"location": "Stanton"})
    assert await store.get_last_open(state, 10, 42) == {"category": "medic", "fields": {"location": "Stanton"}}


def test_default_settings_include_voice_category():
    assert store.DEFAULT_SETTINGS["voice_category_id"] is None


def test_get_settings_defaults_and_overlay():
    assert store.get_settings(None) == store.DEFAULT_SETTINGS
    config = {"settings": {"voice": True}}
    merged = store.get_settings(config)
    assert merged["voice"] is True
    assert merged["idle_warn_minutes"] == 120
    assert config["settings"] == {"voice": True}
