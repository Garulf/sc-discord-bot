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
        "claimer_id": None,
        "status": "open",
        "opened_at": 123.0,
        "closed_at": None,
        "closed_by_id": None,
        "fields": {"location": "Stanton:Hurston:Lorville"},
    }
    await store.save_beacon(state, 99, beacon)
    assert await store.get_beacon(state, 99) == beacon


@pytest.mark.asyncio
async def test_open_beacon_index(state):
    assert await store.get_open_beacon(state, 1, 42, "medic") is None
    await store.set_open_beacon(state, 1, 42, "medic", 99)
    assert await store.get_open_beacon(state, 1, 42, "medic") == 99
    assert await store.get_open_beacon(state, 1, 42, "mining") is None
    await store.clear_open_beacon(state, 1, 42, "medic")
    assert await store.get_open_beacon(state, 1, 42, "medic") is None
