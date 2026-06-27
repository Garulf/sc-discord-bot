"""Handler for /inventory subscribe."""

from __future__ import annotations

import discord

from .subscriptions import _build_live_embed, get_guild_subs, save_guild_subs


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    data = await get_guild_subs(cog, interaction.guild_id)
    if any(sub["channel_id"] == interaction.channel_id for sub in data["subscriptions"]):
        await interaction.response.send_message(
            "This channel already has a live inventory status. Use `/inventory unsubscribe` first.",
            ephemeral=True,
        )
        return

    embed = await _build_live_embed(cog, interaction.guild)
    await interaction.response.defer(ephemeral=True)
    message = await interaction.channel.send(embed=embed)
    data["subscriptions"].append({"channel_id": message.channel.id, "message_id": message.id})
    await save_guild_subs(cog, interaction.guild_id, data)
    await interaction.followup.send("Live inventory status posted — it will update as cards are added.", ephemeral=True)
