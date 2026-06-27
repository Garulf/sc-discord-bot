"""Handler for /inventory add."""

from __future__ import annotations

import discord

from .shared import ITEMS, complete_sets, get_guild_inventory, save_guild_inventory
from .subscriptions import notify_added, refresh_live_status


async def handle(cog, interaction: discord.Interaction, entries: list[tuple[str, int]]) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    for card, count in entries:
        if card not in ITEMS:
            await interaction.response.send_message(
                f"**{card}** is not a valid DCHS item. Choose from DCHS-01 through DCHS-07.",
                ephemeral=True,
            )
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(interaction.user.id)
    user_inv = dict(guild_inv.get(user_key, {}))

    sets_before = complete_sets(user_inv)

    totals: dict[str, int] = {}
    for card, count in entries:
        user_inv[card] = user_inv.get(card, 0) + count
        totals[card] = totals.get(card, 0) + count

    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    sets_after = complete_sets(user_inv)

    sets = sets_after
    if len(totals) == 1:
        card, count = next(iter(totals.items()))
        msg = f"Added ×{count} **{card}** to your inventory. You now have ×{user_inv[card]}."
    else:
        parts = ", ".join(f"×{count} **{card}**" for card, count in totals.items())
        msg = f"Added {parts} to your inventory."
    if sets > 0:
        msg += f" You have **{sets} complete set{'s' if sets != 1 else ''}**!"
    await interaction.response.send_message(msg, ephemeral=True)

    await notify_added(cog, interaction.guild_id, interaction.user, list(totals.items()), sets_before, sets_after)
    await refresh_live_status(cog, interaction.guild_id)
