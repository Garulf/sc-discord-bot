"""Maintenance sweep: escalation pings, idle warnings, and auto-close."""

from __future__ import annotations

import logging

import discord

from . import store
from .lifecycle import close_beacon
from .rules import STATUS_OPEN

logger = logging.getLogger(__name__)


async def _send_best_effort(thread, content: str) -> None:
    try:
        await thread.send(content)
    except discord.HTTPException:
        logger.warning("Could not send maintenance message in beacon thread %s", thread.id)


async def _maybe_escalate(cog, thread, thread_id: int, beacon: dict, config: dict | None, escalate_minutes: int, now: float) -> None:
    if beacon["status"] != STATUS_OPEN or beacon["escalated_at"] is not None:
        return
    if now - beacon["opened_at"] < escalate_minutes * 60:
        return
    role_id = (config or {}).get("roles", {}).get(beacon["category"])
    if role_id:
        content = f"<@&{role_id}> this beacon has had no responders yet."
    else:
        content = "This beacon has had no responders yet. Hit Join if you can help."
    await _send_best_effort(thread, content)
    beacon["escalated_at"] = now
    await store.save_beacon(cog.bot.state, thread_id, beacon)


async def _maybe_warn(cog, thread, thread_id: int, beacon: dict, idle_warn_minutes: int, idle_close_minutes: int, now: float) -> None:
    if beacon["warned_at"] is not None:
        return
    if now - beacon["last_activity_at"] < idle_warn_minutes * 60:
        return
    content = (
        f"<@{beacon['requester_id']}> still need help? This beacon closes automatically "
        f"in {idle_close_minutes} minutes without activity."
    )
    await _send_best_effort(thread, content)
    beacon["warned_at"] = now
    await store.save_beacon(cog.bot.state, thread_id, beacon)


async def _maybe_close(cog, thread, thread_id: int, beacon: dict, idle_close_minutes: int, now: float) -> None:
    if beacon["warned_at"] is None:
        return
    if beacon["last_activity_at"] > beacon["warned_at"]:
        beacon["warned_at"] = None
        await store.save_beacon(cog.bot.state, thread_id, beacon)
        return
    if now - beacon["warned_at"] >= idle_close_minutes * 60:
        await close_beacon(cog, thread, beacon, None)


async def _process_beacon(cog, guild, config: dict | None, settings: dict, thread_id: int, beacon: dict, now: float) -> None:
    thread = guild.get_thread(thread_id) or guild.get_channel(thread_id)
    if thread is None:
        logger.debug("Beacon thread %s no longer resolvable; skipping maintenance", thread_id)
        return
    await _maybe_escalate(cog, thread, thread_id, beacon, config, settings["escalate_minutes"], now)
    await _maybe_warn(cog, thread, thread_id, beacon, settings["idle_warn_minutes"], settings["idle_close_minutes"], now)
    await _maybe_close(cog, thread, thread_id, beacon, settings["idle_close_minutes"], now)


async def run_maintenance(cog, guild, now: float) -> None:
    config = await store.get_config(cog.bot.state, guild.id)
    settings = store.get_settings(config)
    beacons = await store.open_beacons(cog.bot.state, guild.id)
    for thread_id, beacon in beacons:
        try:
            await _process_beacon(cog, guild, config, settings, thread_id, beacon, now)
        except Exception:
            logger.exception("Beacon maintenance failed for thread %s", thread_id)
