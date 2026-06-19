"""Handler for /hangar set."""

from __future__ import annotations

from datetime import UTC, datetime

import discord
from discord import app_commands

from src.exec_hangars import HangarSchedule

from .shared import build_embed, refresh_subscriptions, save_state


async def handle(
    cog,
    interaction: discord.Interaction,
    phase: app_commands.Choice[str],
    lights: int,
) -> None:
    now = datetime.now(UTC)
    if phase.value == "charging":
        cog.schedule = HangarSchedule.from_charging(lights_green=lights, observed_at=now)
    elif phase.value == "active":
        cog.schedule = HangarSchedule.from_active(lights_expired=lights, observed_at=now)
    else:
        cog.schedule = HangarSchedule.from_reset(observed_at=now)

    cog.set_at = now
    await save_state(cog)
    await interaction.response.send_message(
        "Hangar state updated.",
        embed=build_embed(cog.schedule, now, set_at=cog.set_at),
        ephemeral=True,
    )
    await refresh_subscriptions(cog)
