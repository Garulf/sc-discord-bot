"""StateStore keys and accessors for manifests, ids, thread and beacon indexes, and config."""

from __future__ import annotations

from typing import Any

from src.storage import StateStore

from .ledger import Record, normalize


def _record_key(guild_id: int, manifest_id: int) -> str:
    return f"manifest:record:{guild_id}:{manifest_id}"


def _next_id_key(guild_id: int) -> str:
    return f"manifest:next_id:{guild_id}"


def _by_thread_key(thread_id: int) -> str:
    return f"manifest:by_thread:{thread_id}"


def _by_beacon_key(thread_id: int) -> str:
    return f"manifest:by_beacon:{thread_id}"


def _config_key(guild_id: int) -> str:
    return f"manifest:config:{guild_id}"


async def get_record(state: StateStore, guild_id: int, manifest_id: int) -> Record | None:
    raw = await state.get(_record_key(guild_id, manifest_id))
    return normalize(raw) if raw is not None else None


async def save_record(state: StateStore, record: Record) -> None:
    await state.set(_record_key(record["guild_id"], record["id"]), record)


async def delete_record(state: StateStore, record: Record) -> None:
    await state.delete(_record_key(record["guild_id"], record["id"]))
    if record["thread_id"] is not None:
        await state.delete(_by_thread_key(record["thread_id"]))
    if record["beacon_thread_id"] is not None:
        await state.delete(_by_beacon_key(record["beacon_thread_id"]))


async def guild_records(state: StateStore, guild_id: int) -> list[Record]:
    records = []
    for key in await state.keys(f"manifest:record:{guild_id}:"):
        raw = await state.get(key)
        if raw:
            records.append(normalize(raw))
    return sorted(records, key=lambda record: record["id"])


async def allocate_id(state: StateStore, guild_id: int) -> int:
    manifest_id = await state.get(_next_id_key(guild_id), 1)
    await state.set(_next_id_key(guild_id), manifest_id + 1)
    return manifest_id


async def get_by_thread(state: StateStore, thread_id: int) -> int | None:
    return await state.get(_by_thread_key(thread_id))


async def set_by_thread(state: StateStore, thread_id: int, manifest_id: int) -> None:
    await state.set(_by_thread_key(thread_id), manifest_id)


async def get_by_beacon(state: StateStore, thread_id: int) -> int | None:
    return await state.get(_by_beacon_key(thread_id))


async def set_by_beacon(state: StateStore, thread_id: int, manifest_id: int) -> None:
    await state.set(_by_beacon_key(thread_id), manifest_id)


async def get_config(state: StateStore, guild_id: int) -> dict[str, Any] | None:
    return await state.get(_config_key(guild_id))


async def set_config(state: StateStore, guild_id: int, config: dict[str, Any]) -> None:
    await state.set(_config_key(guild_id), config)


async def purge_legacy_loot(state: StateStore) -> int:
    keys = await state.keys("loot:")
    for key in keys:
        await state.delete(key)
    return len(keys)
