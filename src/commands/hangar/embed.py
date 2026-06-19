"""Shared embed builder for all /hangar subcommands."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import discord

from src.exec_hangars import HangarSchedule, build_status, format_relative_time


def build_embed(
    schedule: Optional[HangarSchedule],
    now: Optional[datetime] = None,
    set_at: Optional[datetime] = None,
) -> discord.Embed:
    status = build_status(schedule, now)
    embed = discord.Embed(
        title=status["title"],
        description=status["description"],
        color=status["color"],
    )
    _now = now or datetime.now(timezone.utc)
    updated_str = format_relative_time(_now, _now)
    footer = (
        f"Synced: {format_relative_time(set_at, _now)} • Updated: {updated_str}"
        if set_at
        else f"Updated: {updated_str}"
    )
    embed.set_footer(text=footer)
    return embed
