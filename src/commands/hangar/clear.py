"""Handler for /hangar clear."""

from __future__ import annotations

import discord

from .shared import build_embed, get_schedule_for_guild, refresh_subscriptions, save_state
from .sync import _reset_notify
from .warnings import refresh_event_messages


async def handle(cog, interaction: discord.Interaction) -> None:
    guild_id = interaction.guild_id
    if guild_id not in cog.guild_schedules and guild_id not in cog.guild_set_at:
        await interaction.response.send_message(
            "This server has no hangar override; it already follows the global schedule.",
            ephemeral=True,
        )
        return

    cog.guild_schedules.pop(guild_id, None)
    cog.guild_set_at.pop(guild_id, None)
    await _reset_notify(cog, guild_id)
    await save_state(cog)

    schedule, set_at = get_schedule_for_guild(cog, guild_id)
    await interaction.response.send_message(
        "Server hangar override cleared. Now following the global schedule.",
        embed=build_embed(schedule, set_at=set_at) if schedule else None,
        ephemeral=True,
    )
    await refresh_subscriptions(cog)
    await refresh_event_messages(cog)
