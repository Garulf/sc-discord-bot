"""Handler for /inventory clear."""

from __future__ import annotations

import discord

from .shared import get_guild_inventory, save_guild_inventory


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(interaction.user.id)
    if not guild_inv.get(user_key):
        await interaction.response.send_message("Your inventory is already empty.", ephemeral=True)
        return

    guild_inv.pop(user_key, None)
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)
    await interaction.response.send_message("Your inventory has been cleared.", ephemeral=True)
