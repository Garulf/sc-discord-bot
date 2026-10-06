"""StateStore keys and accessors for loot records, ids, the beacon index, and config."""

from __future__ import annotations

from typing import Any

from src.storage import StateStore

from .ledger import Record, normalize_loot


def _record_key(guild_id: int, loot_id: int) -> str:
    return f"loot:record:{guild_id}:{loot_id}"


def _next_id_key(guild_id: int) -> str:
    return f"loot:next_id:{guild_id}"


def _by_beacon_key(thread_id: int) -> str:
    return f"loot:by_beacon:{thread_id}"


def _config_key(guild_id: int) -> str:
    return f"loot:config:{guild_id}"


async def get_record(state: StateStore, guild_id: int, loot_id: int) -> Record | None:
    raw = await state.get(_record_key(guild_id, loot_id))
    return normalize_loot(raw) if raw is not None else None


async def save_record(state: StateStore, record: Record) -> None:
    await state.set(_record_key(record["guild_id"], record["id"]), record)


async def delete_record(state: StateStore, record: Record) -> None:
    await state.delete(_record_key(record["guild_id"], record["id"]))
    if record["beacon_thread_id"] is not None:
        await state.delete(_by_beacon_key(record["beacon_thread_id"]))


async def guild_records(state: StateStore, guild_id: int) -> list[Record]:
    records = []
    for key in await state.keys(f"loot:record:{guild_id}:"):
        raw = await state.get(key)
        if raw:
            records.append(normalize_loot(raw))
    return sorted(records, key=lambda record: record["id"])


async def allocate_id(state: StateStore, guild_id: int) -> int:
    loot_id = await state.get(_next_id_key(guild_id), 1)
    await state.set(_next_id_key(guild_id), loot_id + 1)
    return loot_id


async def get_by_beacon(state: StateStore, thread_id: int) -> int | None:
    return await state.get(_by_beacon_key(thread_id))


async def set_by_beacon(state: StateStore, thread_id: int, loot_id: int) -> None:
    await state.set(_by_beacon_key(thread_id), loot_id)


async def get_config(state: StateStore, guild_id: int) -> dict[str, Any] | None:
    return await state.get(_config_key(guild_id))


async def set_config(state: StateStore, guild_id: int, config: dict[str, Any]) -> None:
    await state.set(_config_key(guild_id), config)
