"""Shared code for the /hangar command group.

Contains the embed builder and state-persistence helpers used by all hangar
subcommands.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import discord

logger = logging.getLogger(__name__)

from src.exec_hangars import HangarSchedule, build_status, format_relative_time

_STATE_KEY = "hangar"


def build_embed(
    schedule: HangarSchedule | None,
    now: datetime | None = None,
    set_at: datetime | None = None,
) -> discord.Embed:
    status = build_status(schedule, now)
    embed = discord.Embed(
        title=status["title"],
        description=status["description"],
        color=status["color"],
    )
    _now = now or datetime.now(UTC)
    updated_str = format_relative_time(_now, _now)
    footer = (
        f"Synced: {format_relative_time(set_at, _now)} • Updated: {updated_str}"
        if set_at
        else f"Updated: {updated_str}"
    )
    embed.set_footer(text=footer)
    return embed


async def load_state(cog) -> None:
    data = await cog.bot.state.get(_STATE_KEY)
    if data is None:
        return
    cycle_start = data.get("cycle_start")
    if cycle_start:
        cog.schedule = HangarSchedule(datetime.fromisoformat(cycle_start))
    set_at = data.get("set_at")
    if set_at:
        cog.set_at = datetime.fromisoformat(set_at)
    cog.subscriptions = data.get("subscriptions", [])


async def save_state(cog) -> None:
    data = {
        "cycle_start": cog.schedule.cycle_start.isoformat() if cog.schedule else None,
        "set_at": cog.set_at.isoformat() if cog.set_at else None,
        "subscriptions": cog.subscriptions,
    }
    await cog.bot.state.set(_STATE_KEY, data)


async def refresh_subscriptions(cog) -> None:
    """Edit every subscribed message with the current status, pruning dead ones."""
    if cog.schedule is None or not cog.subscriptions:
        return

    embed = build_embed(cog.schedule, set_at=cog.set_at)
    survivors: list[dict] = []
    changed = False
    for sub in cog.subscriptions:
        channel = cog.bot.get_channel(sub["channel_id"])
        if channel is None:
            try:
                channel = await cog.bot.fetch_channel(sub["channel_id"])
            except (discord.NotFound, discord.Forbidden):
                changed = True
                continue
            except discord.HTTPException as exc:
                logger.warning("Failed to fetch channel for hangar subscription %s: %s", sub, exc)
                survivors.append(sub)
                continue
        try:
            message = await channel.fetch_message(sub["message_id"])
            await message.edit(embed=embed)
            survivors.append(sub)
        except discord.NotFound:
            changed = True
        except discord.Forbidden:
            survivors.append(sub)
        except discord.HTTPException as exc:
            logger.warning("Failed to update hangar subscription %s: %s", sub, exc)
            survivors.append(sub)

    if changed:
        cog.subscriptions[:] = survivors
        await save_state(cog)
