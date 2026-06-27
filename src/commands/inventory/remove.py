"""Handler for /inventory remove item."""

from __future__ import annotations

import discord

from .shared import ITEMS, get_guild_inventory, save_guild_inventory
from .subscriptions import refresh_live_status


async def handle(cog, interaction: discord.Interaction, entries: list[tuple[str, int]]) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    for card, count in entries:
        if card not in ITEMS:
            await interaction.response.send_message(f"**{card}** is not a valid DCHS item.", ephemeral=True)
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(interaction.user.id)
    user_inv = dict(guild_inv.get(user_key, {}))

    # Tally requested removals per card before touching inventory
    totals: dict[str, int] = {}
    for card, count in entries:
        totals[card] = totals.get(card, 0) + count

    for card, count in totals.items():
        have = user_inv.get(card, 0)
        if have < count:
            await interaction.response.send_message(
                f"You only have ×{have} **{card}** but tried to remove ×{count}.", ephemeral=True
            )
            return

    removed_parts = []
    for card, count in totals.items():
        user_inv[card] = user_inv[card] - count
        if user_inv[card] == 0:
            del user_inv[card]
        removed_parts.append((card, count, user_inv.get(card, 0)))

    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)
    await refresh_live_status(cog, interaction.guild_id)

    if len(removed_parts) == 1:
        card, count, remaining = removed_parts[0]
        msg = f"Removed ×{count} **{card}** from your inventory. You now have ×{remaining}."
    else:
        parts = ", ".join(f"×{count} **{card}**" for card, count, _ in removed_parts)
        msg = f"Removed {parts} from your inventory."
    await interaction.response.send_message(msg, ephemeral=True)
