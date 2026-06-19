"""Handler for /inventory clear."""

from __future__ import annotations

import discord


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    guild_inv = await cog._get_guild_inventory(interaction.guild_id)
    user_key = str(interaction.user.id)
    if not guild_inv.get(user_key):
        await interaction.response.send_message("Your inventory is already empty.", ephemeral=True)
        return

    guild_inv.pop(user_key, None)
    await cog._save_guild_inventory(interaction.guild_id, guild_inv)
    await interaction.response.send_message("Your inventory has been cleared.", ephemeral=True)
