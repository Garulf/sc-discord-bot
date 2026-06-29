"""Manage per-channel event notification messages for hangar open/close transitions."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import discord

from src.exec_hangars import HangarPhase
from src.exec_hangars.constants import ACTIVE_DURATION, CHARGING_DURATION, RESET_DURATION

from .shared import get_schedule_for_guild, save_state

logger = logging.getLogger(__name__)

WARNING_WINDOW = timedelta(minutes=5)


def _ts(dt: datetime) -> str:
    return f"<t:{int(dt.timestamp())}:R>"


def _open_time(schedule, now: datetime) -> datetime:
    """When the current (or most recent) ACTIVE phase started."""
    return schedule.next_close(now) - ACTIVE_DURATION


def _close_time(schedule, now: datetime) -> datetime:
    """When the current non-ACTIVE phase started (i.e. when hangar last closed)."""
    return schedule.next_open(now) - CHARGING_DURATION - RESET_DURATION


async def _post(channel: discord.TextChannel, text: str) -> int | None:
    try:
        msg = await channel.send(text)
        return msg.id
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Failed to post hangar notification to %s: %s", channel.id, exc)
        return None


async def _edit(channel: discord.TextChannel, message_id: int, text: str) -> bool:
    """Edit a message. Returns False if the message no longer exists."""
    try:
        msg = await channel.fetch_message(message_id)
        await msg.edit(content=text)
        return True
    except discord.NotFound:
        return False
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Failed to edit hangar notification %s: %s", message_id, exc)
        return True


async def _delete(channel: discord.TextChannel, message_id: int | None) -> None:
    if message_id is None:
        return
    try:
        msg = await channel.fetch_message(message_id)
        await msg.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


async def _ensure(channel, mid: int | None, text: str) -> int | None:
    """Edit existing message, or post a new one if it was deleted."""
    if mid and await _edit(channel, mid, text):
        return mid
    return await _post(channel, text)


async def refresh_event_messages(cog) -> None:
    if not cog.subscriptions:
        return

    now = datetime.now(UTC)
    changed = False

    for sub in cog.subscriptions:
        schedule, _ = get_schedule_for_guild(cog, sub.get("guild_id"))
        if schedule is None:
            continue

        channel_id = sub["channel_id"]
        channel = cog.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await cog.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue

        snapshot = schedule.snapshot(now)
        phase = snapshot.phase

        state = sub.get("notify_state")
        mid = sub.get("notify_message_id")
        new_state = state
        new_mid = mid

        if state is None:
            if phase is HangarPhase.ACTIVE and snapshot.time_until_close <= WARNING_WINDOW:
                next_close = schedule.next_close(now)
                new_mid = await _post(channel, f"⚠️ Executive Hangar closes {_ts(next_close)}!")
                new_state = "close_warning"
            elif phase is not HangarPhase.ACTIVE and snapshot.time_until_open <= WARNING_WINDOW:
                next_open = schedule.next_open(now)
                new_mid = await _post(channel, f"⚠️ Executive Hangar opens {_ts(next_open)}!")
                new_state = "open_warning"

        elif state == "open_warning":
            if phase is HangarPhase.ACTIVE:
                text = f"🟩 Executive Hangar opened {_ts(_open_time(schedule, now))}!"
                new_mid = await _ensure(channel, mid, text)
                new_state = "open"

        elif state == "open":
            if phase is not HangarPhase.ACTIVE:
                text = f"🟥 Executive Hangar closed {_ts(_close_time(schedule, now))}."
                new_mid = await _ensure(channel, mid, text)
                new_state = "closed"
            elif snapshot.time_until_close <= WARNING_WINDOW:
                next_close = schedule.next_close(now)
                await _delete(channel, mid)
                new_mid = await _post(channel, f"⚠️ Executive Hangar closes {_ts(next_close)}!")
                new_state = "close_warning"

        elif state == "close_warning":
            if phase is not HangarPhase.ACTIVE:
                text = f"🟥 Executive Hangar closed {_ts(_close_time(schedule, now))}."
                new_mid = await _ensure(channel, mid, text)
                new_state = "closed"

        elif state == "closed":
            if phase is HangarPhase.ACTIVE:
                text = f"🟩 Executive Hangar opened {_ts(_open_time(schedule, now))}!"
                new_mid = await _ensure(channel, mid, text)
                new_state = "open"
            elif snapshot.time_until_open <= WARNING_WINDOW:
                next_open = schedule.next_open(now)
                await _delete(channel, mid)
                new_mid = await _post(channel, f"⚠️ Executive Hangar opens {_ts(next_open)}!")
                new_state = "open_warning"

        if new_state != state or new_mid != mid:
            sub["notify_state"] = new_state
            sub["notify_message_id"] = new_mid
            changed = True

    if changed:
        await save_state(cog)
