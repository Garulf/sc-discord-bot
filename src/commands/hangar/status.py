"""Handler for /hangar status."""

from __future__ import annotations

import discord

from .shared import build_embed, get_schedule_for_guild


async def handle(cog, interaction: discord.Interaction) -> None:
    schedule, set_at = get_schedule_for_guild(cog, interaction.guild_id)
    if schedule is None:
        await interaction.response.send_message(
            "No hangar schedule set. Use `/hangar set` or ask the bot owner to configure a global schedule.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(embed=build_embed(schedule, set_at=set_at), ephemeral=True)
