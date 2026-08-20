"""StateStore keys and accessors for beacon config, records, and open index."""

from __future__ import annotations

from typing import Any

from src.storage import StateStore

from .rules import STATUS_CLOSED, normalize_beacon


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
    beacon = await state.get(_beacon_key(thread_id))
    return normalize_beacon(beacon) if beacon is not None else None


async def save_beacon(state: StateStore, thread_id: int, beacon: dict[str, Any]) -> None:
    await state.set(_beacon_key(thread_id), beacon)


async def get_open_beacon(state: StateStore, guild_id: int, user_id: int, category: str) -> int | None:
    return await state.get(_open_key(guild_id, user_id, category))


async def set_open_beacon(state: StateStore, guild_id: int, user_id: int, category: str, thread_id: int) -> None:
    await state.set(_open_key(guild_id, user_id, category), thread_id)


async def clear_open_beacon(state: StateStore, guild_id: int, user_id: int, category: str) -> None:
    await state.delete(_open_key(guild_id, user_id, category))


DEFAULT_SETTINGS: dict[str, Any] = {
    "idle_warn_minutes": 120,
    "idle_close_minutes": 60,
    "escalate_minutes": 15,
    "voice": False,
    "voice_category_id": None,
    "digest_channel_id": None,
}


def get_settings(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_SETTINGS)
    if config:
        merged.update(config.get("settings") or {})
    return merged


async def _beacons(state: StateStore, guild_id: int, *, include_closed: bool) -> list[tuple[int, dict[str, Any]]]:
    results = []
    for key in await state.keys("beacons:beacon:"):
        raw = await state.get(key)
        if not raw or raw.get("guild_id") != guild_id:
            continue
        beacon = normalize_beacon(raw)
        if not include_closed and beacon["status"] == STATUS_CLOSED:
            continue
        results.append((int(key.rsplit(":", 1)[-1]), beacon))
    return results


async def open_beacons(state: StateStore, guild_id: int) -> list[tuple[int, dict[str, Any]]]:
    return await _beacons(state, guild_id, include_closed=False)


async def all_beacons(state: StateStore, guild_id: int) -> list[tuple[int, dict[str, Any]]]:
    return await _beacons(state, guild_id, include_closed=True)


def _rep_key(guild_id: int, user_id: int) -> str:
    return f"beacons:rep:{guild_id}:{user_id}"


async def add_rep(state: StateStore, guild_id: int, user_id: int, amount: int = 1) -> int:
    total = (await state.get(_rep_key(guild_id, user_id)) or 0) + amount
    await state.set(_rep_key(guild_id, user_id), total)
    return total


async def get_reps(state: StateStore, guild_id: int) -> dict[int, int]:
    reps = {}
    for key in await state.keys(f"beacons:rep:{guild_id}:"):
        reps[int(key.rsplit(":", 1)[-1])] = await state.get(key) or 0
    return reps


def _last_key(guild_id: int, user_id: int) -> str:
    return f"beacons:last:{guild_id}:{user_id}"


async def set_last_open(state: StateStore, guild_id: int, user_id: int, category: str, fields: dict[str, Any]) -> None:
    await state.set(_last_key(guild_id, user_id), {"category": category, "fields": fields})


async def get_last_open(state: StateStore, guild_id: int, user_id: int) -> dict[str, Any] | None:
    return await state.get(_last_key(guild_id, user_id))


_LEGACY_PREFIXES = {
    "tickets:config:": "beacons:config:",
    "tickets:ticket:": "beacons:beacon:",
    "tickets:open:": "beacons:open:",
}


async def migrate_legacy_keys(state: StateStore) -> None:
    """Copy pre-rename ticket state to beacon keys.

    Legacy keys are left in place so a rollback to a pre-rename release
    still finds its data; existing beacon keys are never overwritten.
    """
    for old_prefix, new_prefix in _LEGACY_PREFIXES.items():
        for key in await state.keys(old_prefix):
            new_key = new_prefix + key.removeprefix(old_prefix)
            if await state.get(new_key) is None:
                await state.set(new_key, await state.get(key))
