"""Handler for /inventory remove."""

from __future__ import annotations

import discord

from .helpers import ITEMS


async def handle(cog, interaction: discord.Interaction, item: str, count: int = 1) -> None:
    if item not in ITEMS:
        await interaction.response.send_message(f"**{item}** is not a valid DCHS item.", ephemeral=True)
        return
    if count < 1:
        await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
        return
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    guild_inv = await cog._get_guild_inventory(interaction.guild_id)
    user_key = str(interaction.user.id)
    user_inv = dict(guild_inv.get(user_key, {}))
    current_count = user_inv.get(item, 0)
    if current_count <= 0:
        await interaction.response.send_message(f"You don't have **{item}** in your inventory.", ephemeral=True)
        return

    removed = min(count, current_count)
    user_inv[item] = current_count - removed
    if user_inv[item] == 0:
        del user_inv[item]
    guild_inv[user_key] = user_inv
    await cog._save_guild_inventory(interaction.guild_id, guild_inv)

    remaining = user_inv.get(item, 0)
    await interaction.response.send_message(
        f"Removed ×{removed} **{item}** from your inventory. You now have ×{remaining}.",
        ephemeral=True,
    )
