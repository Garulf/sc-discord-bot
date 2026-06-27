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


def get_schedule_for_guild(cog, guild_id: int | None) -> tuple[HangarSchedule | None, datetime | None]:
    """Return the guild's override schedule if set, else the global schedule."""
    if guild_id is not None and guild_id in cog.guild_schedules:
        return cog.guild_schedules[guild_id], cog.guild_set_at.get(guild_id)
    return cog.global_schedule, cog.global_set_at


async def load_state(cog) -> None:
    data = await cog.bot.state.get(_STATE_KEY)
    if data is None:
        return

    # Migration: old format stored cycle_start/set_at at top level
    if data.get("cycle_start") and "global" not in data:
        data["global"] = {"cycle_start": data["cycle_start"], "set_at": data.get("set_at")}

    global_data = data.get("global") or {}
    if global_data.get("cycle_start"):
        cog.global_schedule = HangarSchedule(datetime.fromisoformat(global_data["cycle_start"]))
    if global_data.get("set_at"):
        cog.global_set_at = datetime.fromisoformat(global_data["set_at"])

    for gid_str, gdata in (data.get("guilds") or {}).items():
        gid = int(gid_str)
        if gdata.get("cycle_start"):
            cog.guild_schedules[gid] = HangarSchedule(datetime.fromisoformat(gdata["cycle_start"]))
        if gdata.get("set_at"):
            cog.guild_set_at[gid] = datetime.fromisoformat(gdata["set_at"])

    cog.subscriptions = data.get("subscriptions", [])
    cog.warnings = data.get("warnings", {})


async def save_state(cog) -> None:
    guilds_data = {}
    for gid in set(cog.guild_schedules) | set(cog.guild_set_at):
        sched = cog.guild_schedules.get(gid)
        guilds_data[str(gid)] = {
            "cycle_start": sched.cycle_start.isoformat() if sched else None,
            "set_at": cog.guild_set_at[gid].isoformat() if gid in cog.guild_set_at else None,
        }
    data = {
        "global": {
            "cycle_start": cog.global_schedule.cycle_start.isoformat() if cog.global_schedule else None,
            "set_at": cog.global_set_at.isoformat() if cog.global_set_at else None,
        },
        "guilds": guilds_data,
        "subscriptions": cog.subscriptions,
        "warnings": cog.warnings,
    }
    await cog.bot.state.set(_STATE_KEY, data)


async def refresh_subscriptions(cog) -> None:
    """Edit every subscribed message with the current status, pruning dead ones."""
    if not cog.subscriptions:
        return

    survivors: list[dict] = []
    changed = False
    for sub in cog.subscriptions:
        schedule, set_at = get_schedule_for_guild(cog, sub.get("guild_id"))
        if schedule is None:
            survivors.append(sub)
            continue
        embed = build_embed(schedule, set_at=set_at)
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
