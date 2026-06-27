"""Handler for /inventory unsubscribe."""

from __future__ import annotations

import discord

from .subscriptions import get_guild_subs, save_guild_subs


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    data = await get_guild_subs(cog, interaction.guild_id)
    channel_subs = [s for s in data["subscriptions"] if s["channel_id"] == interaction.channel_id]
    if not channel_subs:
        await interaction.response.send_message("No live inventory status found in this channel.", ephemeral=True)
        return

    data["subscriptions"] = [s for s in data["subscriptions"] if s["channel_id"] != interaction.channel_id]

    for sub in channel_subs:
        try:
            msg = await interaction.channel.fetch_message(sub["message_id"])
            await msg.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    await save_guild_subs(cog, interaction.guild_id, data)
    await interaction.response.send_message("Live inventory status removed.", ephemeral=True)
