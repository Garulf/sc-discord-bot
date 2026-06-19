"""Handler for /inventory add."""

from __future__ import annotations

import discord

from .shared import ITEMS, complete_sets, get_guild_inventory, save_guild_inventory


async def handle(cog, interaction: discord.Interaction, item: str, count: int = 1) -> None:
    if item not in ITEMS:
        await interaction.response.send_message(
            f"**{item}** is not a valid DCHS item. Choose from DCHS-01 through DCHS-07.",
            ephemeral=True,
        )
        return
    if count < 1:
        await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
        return
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(interaction.user.id)
    user_inv = dict(guild_inv.get(user_key, {}))
    user_inv[item] = user_inv.get(item, 0) + count
    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    total = user_inv[item]
    sets = complete_sets(user_inv)
    msg = f"Added ×{count} **{item}** to your inventory. You now have ×{total}."
    if sets > 0:
        msg += f" You have **{sets} complete set{'s' if sets != 1 else ''}**!"
    await interaction.response.send_message(msg, ephemeral=True)
