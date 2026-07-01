"""Handler for /hangar global set (bot owner only)."""

from __future__ import annotations

from datetime import UTC, datetime

import discord
from discord import app_commands

from src.exec_hangars import HangarSchedule

from .global_sync import _reset_global_notify
from .shared import build_embed, refresh_subscriptions, save_state
from .warnings import refresh_event_messages


async def handle(
    cog,
    interaction: discord.Interaction,
    phase: app_commands.Choice[str],
    lights: int,
) -> None:
    now = datetime.now(UTC)
    if phase.value == "charging":
        cog.global_schedule = HangarSchedule.from_charging(lights_green=lights, observed_at=now)
    elif phase.value == "active":
        cog.global_schedule = HangarSchedule.from_active(lights_expired=lights, observed_at=now)
    else:
        cog.global_schedule = HangarSchedule.from_reset(observed_at=now)

    cog.global_set_at = now

    await _reset_global_notify(cog)
    await save_state(cog)
    await interaction.response.send_message(
        "Global hangar state updated. Servers without a local override will use this schedule.",
        embed=build_embed(cog.global_schedule, now, set_at=cog.global_set_at),
        ephemeral=True,
    )
    await refresh_subscriptions(cog)
    await refresh_event_messages(cog)
