"""Handler for /inventory remove item."""

from __future__ import annotations

from collections import Counter

import discord

from .shared import ITEMS, get_guild_inventory, save_guild_inventory


async def handle(cog, interaction: discord.Interaction, items: list[str]) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    for item in items:
        if item not in ITEMS:
            await interaction.response.send_message(f"**{item}** is not a valid DCHS item.", ephemeral=True)
            return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(interaction.user.id)
    user_inv = dict(guild_inv.get(user_key, {}))

    counts = Counter(items)
    for item, count in counts.items():
        if user_inv.get(item, 0) < count:
            have = user_inv.get(item, 0)
            await interaction.response.send_message(
                f"You only have ×{have} **{item}** but tried to remove ×{count}.", ephemeral=True
            )
            return

    removed_parts = []
    for item, count in counts.items():
        user_inv[item] = user_inv[item] - count
        if user_inv[item] == 0:
            del user_inv[item]
        removed_parts.append((item, count))

    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    if len(removed_parts) == 1:
        item, count = removed_parts[0]
        remaining = user_inv.get(item, 0)
        msg = f"Removed ×{count} **{item}** from your inventory. You now have ×{remaining}."
    else:
        parts = ", ".join(f"×{count} **{item}**" for item, count in removed_parts)
        msg = f"Removed {parts} from your inventory."
    await interaction.response.send_message(msg, ephemeral=True)
