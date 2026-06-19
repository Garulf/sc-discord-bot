"""Handler for /hangar subscribe."""

from __future__ import annotations

import discord

from .shared import build_embed, save_state


async def handle(cog, interaction: discord.Interaction) -> None:
    if cog.schedule is None:
        await interaction.response.send_message(
            "Hangar state hasn't been set yet. Use `/hangar set` first.", ephemeral=True
        )
        return

    message = await interaction.channel.send(embed=build_embed(cog.schedule, set_at=cog.set_at))
    cog.subscriptions.append({"channel_id": message.channel.id, "message_id": message.id})
    await save_state(cog)
    await interaction.response.send_message("Live status posted — it will keep updating here.", ephemeral=True)
