import pytest

from src.commands.manifest import ledger, store
from src.storage import Database, StateStore


@pytest.fixture
async def state(tmp_path):
    db = Database(str(tmp_path / "manifest.db"))
    await db.connect()
    yield StateStore(db)
    await db.close()


def _record(manifest_id=1, guild_id=7, beacon_thread_id=None):
    return ledger.new_manifest(
        manifest_id=manifest_id,
        guild_id=guild_id,
        created_by=1,
        carrier_id=1,
        crew_ids=[2],
        cargo=[{"commodity": "Gold", "scu": 1, "est_price": None}],
        costs=[],
        now=0.0,
        beacon_thread_id=beacon_thread_id,
    )


async def test_save_and_get_round_trip(state):
    record = _record()
    await store.save_record(state, record)
    assert await store.get_record(state, 7, 1) == record
    assert await store.get_record(state, 7, 2) is None


async def test_guild_records_sorted_and_scoped(state):
    for manifest_id in (3, 1, 2):
        await store.save_record(state, _record(manifest_id))
    await store.save_record(state, _record(9, guild_id=8))
    assert [r["id"] for r in await store.guild_records(state, 7)] == [1, 2, 3]


async def test_allocate_id_counts_per_guild(state):
    assert await store.allocate_id(state, 7) == 1
    assert await store.allocate_id(state, 7) == 2
    assert await store.allocate_id(state, 8) == 1


async def test_indexes_cleared_on_delete(state):
    record = _record(beacon_thread_id=50)
    record["thread_id"] = 60
    await store.save_record(state, record)
    await store.set_by_thread(state, 60, 1)
    await store.set_by_beacon(state, 50, 1)
    assert await store.get_by_thread(state, 60) == 1
    assert await store.get_by_beacon(state, 50) == 1
    await store.delete_record(state, record)
    assert await store.get_record(state, 7, 1) is None
    assert await store.get_by_thread(state, 60) is None
    assert await store.get_by_beacon(state, 50) is None


async def test_config_round_trip(state):
    assert await store.get_config(state, 7) is None
    await store.set_config(state, 7, {"channel_id": 5})
    assert await store.get_config(state, 7) == {"channel_id": 5}


async def test_purge_legacy_loot_only_removes_loot_keys(state):
    await state.set("loot:record:7:1", {"id": 1})
    await state.set("loot:next_id:7", 2)
    await state.set("beacons:beacon:1", {"x": 1})
    await store.save_record(state, _record())
    assert await store.purge_legacy_loot(state) == 2
    assert await state.keys("loot:") == []
    assert await state.get("beacons:beacon:1") == {"x": 1}
    assert await store.get_record(state, 7, 1) is not None
    assert await store.purge_legacy_loot(state) == 0
