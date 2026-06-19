"""Shared embed builder for all /hangar subcommands."""

from __future__ import annotations

from datetime import UTC, datetime

import discord

from src.exec_hangars import HangarSchedule, build_status, format_relative_time


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
