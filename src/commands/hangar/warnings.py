"""Post 5-minute advance warnings for hangar open/close events; clean up on status change."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import discord

from src.exec_hangars import HangarPhase

from .shared import get_schedule_for_guild, save_state

logger = logging.getLogger(__name__)

WARNING_WINDOW = timedelta(minutes=5)

_EVENTS = [
    ("open", "🟢 The Executive Hangar is opening in ~5 minutes!"),
    ("close", "🔴 The Executive Hangar is closing in ~5 minutes!"),
]


async def refresh_warnings(cog) -> None:
    if not cog.subscriptions:
        return

    now = datetime.now(UTC)
    changed = False

    for sub in cog.subscriptions:
        schedule, _ = get_schedule_for_guild(cog, sub.get("guild_id"))
        if schedule is None:
            continue

        event_times = {
            "open": schedule.next_open(now),
            "close": schedule.next_close(now),
        }

        channel_id = sub["channel_id"]
        channel_key = str(channel_id)
        channel_warnings: dict = cog.warnings.setdefault(channel_key, {})

        channel = cog.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await cog.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue

        for event_name, message_text in _EVENTS:
            event_time = event_times[event_name]
            time_until = event_time - now
            existing = channel_warnings.get(event_name)

            if existing:
                stored_time = datetime.fromisoformat(existing["event_time"])
                snapshot = schedule.snapshot(now)
                status_unchanged = (event_name == "open" and snapshot.phase != HangarPhase.ACTIVE) or (
                    event_name == "close" and snapshot.phase == HangarPhase.ACTIVE
                )
                # Keep the warning if it's for this exact event and status hasn't changed yet
                if stored_time == event_time and status_unchanged:
                    continue
                # Otherwise delete it (status changed or a new cycle started)
                try:
                    msg = await channel.fetch_message(existing["message_id"])
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
                del channel_warnings[event_name]
                changed = True

            # Post a new warning if we've entered the 5-minute window
            if event_name not in channel_warnings and timedelta(0) < time_until <= WARNING_WINDOW:
                try:
                    msg = await channel.send(message_text)
                    channel_warnings[event_name] = {
                        "message_id": msg.id,
                        "event_time": event_time.isoformat(),
                    }
                    changed = True
                except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                    logger.warning("Failed to post hangar warning to channel %s: %s", channel_id, exc)

    # Prune empty channel entries
    cog.warnings = {k: v for k, v in cog.warnings.items() if v}

    if changed:
        await save_state(cog)
