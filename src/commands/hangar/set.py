"""Handler for /hangar set."""

from __future__ import annotations

from datetime import UTC, datetime

import discord
from discord import app_commands

from src.exec_hangars import HangarSchedule

from .shared import build_embed, get_schedule_for_guild, refresh_subscriptions, save_state


async def handle(
    cog,
    interaction: discord.Interaction,
    phase: app_commands.Choice[str],
    lights: int,
) -> None:
    now = datetime.now(UTC)
    guild_id = interaction.guild_id

    if phase.value == "charging":
        cog.guild_schedules[guild_id] = HangarSchedule.from_charging(lights_green=lights, observed_at=now)
    elif phase.value == "active":
        cog.guild_schedules[guild_id] = HangarSchedule.from_active(lights_expired=lights, observed_at=now)
    else:
        cog.guild_schedules[guild_id] = HangarSchedule.from_reset(observed_at=now)

    cog.guild_set_at[guild_id] = now
    await save_state(cog)

    schedule, set_at = get_schedule_for_guild(cog, guild_id)
    await interaction.response.send_message(
        "Hangar state updated.",
        embed=build_embed(schedule, now, set_at=set_at),
        ephemeral=True,
    )
    await refresh_subscriptions(cog)
