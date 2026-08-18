"""StateStore keys and accessors for beacon config, records, and open index."""

from __future__ import annotations

from typing import Any

from src.storage import StateStore


def _config_key(guild_id: int) -> str:
    return f"beacons:config:{guild_id}"


def _beacon_key(thread_id: int) -> str:
    return f"beacons:beacon:{thread_id}"


def _open_key(guild_id: int, user_id: int, category: str) -> str:
    return f"beacons:open:{guild_id}:{user_id}:{category}"


async def get_config(state: StateStore, guild_id: int) -> dict[str, Any] | None:
    return await state.get(_config_key(guild_id))


async def set_config(state: StateStore, guild_id: int, config: dict[str, Any]) -> None:
    await state.set(_config_key(guild_id), config)


async def get_beacon(state: StateStore, thread_id: int) -> dict[str, Any] | None:
    return await state.get(_beacon_key(thread_id))


async def save_beacon(state: StateStore, thread_id: int, beacon: dict[str, Any]) -> None:
    await state.set(_beacon_key(thread_id), beacon)


async def get_open_beacon(state: StateStore, guild_id: int, user_id: int, category: str) -> int | None:
    return await state.get(_open_key(guild_id, user_id, category))


async def set_open_beacon(state: StateStore, guild_id: int, user_id: int, category: str, thread_id: int) -> None:
    await state.set(_open_key(guild_id, user_id, category), thread_id)


async def clear_open_beacon(state: StateStore, guild_id: int, user_id: int, category: str) -> None:
    await state.delete(_open_key(guild_id, user_id, category))
