"""Handler for /inventory remove item."""

from __future__ import annotations

import discord

from .shared import ITEMS, get_guild_inventory, save_guild_inventory


async def handle(cog, interaction: discord.Interaction, entries: list[tuple[str, int]]) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    for item, count in entries:
        if item not in ITEMS:
            await interaction.response.send_message(f"**{item}** is not a valid DCHS item.", ephemeral=True)
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(interaction.user.id)
    user_inv = dict(guild_inv.get(user_key, {}))

    for item, count in entries:
        if user_inv.get(item, 0) <= 0:
            await interaction.response.send_message(f"You don't have **{item}** in your inventory.", ephemeral=True)
            return

    removed_parts = []
    for item, count in entries:
        current = user_inv.get(item, 0)
        removed = min(count, current)
        user_inv[item] = current - removed
        if user_inv[item] == 0:
            del user_inv[item]
        removed_parts.append((item, removed, user_inv.get(item, 0)))

    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    if len(removed_parts) == 1:
        item, removed, remaining = removed_parts[0]
        msg = f"Removed ×{removed} **{item}** from your inventory. You now have ×{remaining}."
    else:
        parts = ", ".join(f"×{removed} **{item}**" for item, removed, _ in removed_parts)
        msg = f"Removed {parts} from your inventory."
    await interaction.response.send_message(msg, ephemeral=True)
