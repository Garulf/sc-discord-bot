"""Handler for /hangar subscribe."""

from __future__ import annotations

import discord

from .shared import build_embed, get_schedule_for_guild, save_state


async def handle(cog, interaction: discord.Interaction) -> None:
    schedule, set_at = get_schedule_for_guild(cog, interaction.guild_id)
    if schedule is None:
        await interaction.response.send_message(
            "No hangar schedule set. Use `/hangar set` or ask the bot owner to configure a global schedule.",
            ephemeral=True,
        )
        return

    if any(sub["channel_id"] == interaction.channel_id for sub in cog.subscriptions):
        await interaction.response.send_message(
            "This channel already has a live status. Use `/hangar unsubscribe` first.", ephemeral=True
        )
        return

    message = await interaction.channel.send(embed=build_embed(schedule, set_at=set_at))
    cog.subscriptions.append(
        {
            "channel_id": message.channel.id,
            "message_id": message.id,
            "guild_id": interaction.guild_id,
        }
    )
    await save_state(cog)
    await interaction.response.send_message("Live status posted — it will keep updating here.", ephemeral=True)
