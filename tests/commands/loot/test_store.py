import pytest

from src.commands.loot import ledger, store
from src.storage import Database, StateStore


@pytest.fixture
async def state(tmp_path):
    db = Database(str(tmp_path / "loot.db"))
    await db.connect()
    yield StateStore(db)
    await db.close()


def _record(loot_id, guild_id=1, beacon_thread_id=None):
    return ledger.new_record(
        loot_id=loot_id,
        guild_id=guild_id,
        title="t",
        created_by=5,
        participants=[5],
        organizer_ids=[5],
        now=0.0,
        beacon_thread_id=beacon_thread_id,
    )


@pytest.mark.asyncio
async def test_record_roundtrip_keeps_int_user_ids(state):
    record = _record(3)
    ledger.add_cargo(record, "Gold", 10, holder_id=5)
    ledger.record_sale(record, ledger.find_line(record, "Gold"), scu=10, total=100, now=1.0)
    await store.save_record(state, record)
    loaded = await store.get_record(state, 1, 3)
    assert loaded == record
    assert isinstance(loaded["sales"][0]["payouts"][0]["user_id"], int)


@pytest.mark.asyncio
async def test_get_missing_record(state):
    assert await store.get_record(state, 1, 99) is None


@pytest.mark.asyncio
async def test_guild_records_are_scoped_and_sorted(state):
    await store.save_record(state, _record(2, guild_id=1))
    await store.save_record(state, _record(1, guild_id=1))
    await store.save_record(state, _record(1, guild_id=11))
    ids = [r["id"] for r in await store.guild_records(state, 1)]
    assert ids == [1, 2]


@pytest.mark.asyncio
async def test_allocate_id_counts_per_guild(state):
    assert [await store.allocate_id(state, 1) for _ in range(3)] == [1, 2, 3]
    assert await store.allocate_id(state, 2) == 1


@pytest.mark.asyncio
async def test_beacon_index_and_delete(state):
    record = _record(4, beacon_thread_id=777)
    await store.save_record(state, record)
    await store.set_by_beacon(state, 777, 4)
    assert await store.get_by_beacon(state, 777) == 4
    await store.delete_record(state, record)
    assert await store.get_record(state, 1, 4) is None
    assert await store.get_by_beacon(state, 777) is None


@pytest.mark.asyncio
async def test_config_roundtrip(state):
    assert await store.get_config(state, 1) is None
    await store.set_config(state, 1, {"channel_id": 55})
    assert await store.get_config(state, 1) == {"channel_id": 55}
