"""Handler for /inventory remove set."""

from __future__ import annotations

import discord

from .shared import ITEMS, complete_sets, get_guild_inventory, save_guild_inventory


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(interaction.user.id)
    user_inv = dict(guild_inv.get(user_key, {}))

    if complete_sets(user_inv) < 1:
        await interaction.response.send_message("You don't have a complete set to remove.", ephemeral=True)
        return

    for item in ITEMS:
        user_inv[item] = user_inv[item] - 1
        if user_inv[item] == 0:
            del user_inv[item]

    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)
    await interaction.response.send_message("Removed one complete set (DCHS-01 through DCHS-07) from your inventory.", ephemeral=True)
