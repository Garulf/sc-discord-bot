"""Handler for /inventory admin add."""

from __future__ import annotations

import discord

from ..shared import ITEMS, complete_sets, get_guild_inventory, save_guild_inventory


async def handle(cog, interaction: discord.Interaction, member: discord.Member, entries: list[tuple[str, int]]) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    for item, count in entries:
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    user_key = str(member.id)
    user_inv = dict(guild_inv.get(user_key, {}))

    totals: dict[str, int] = {}
    for item, count in entries:
        user_inv[item] = user_inv.get(item, 0) + count
        totals[item] = totals.get(item, 0) + count

    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    sets = complete_sets(user_inv)
    if len(totals) == 1:
        item, count = next(iter(totals.items()))
        msg = f"Added ×{count} **{item}** to {member.display_name}'s inventory. They now have ×{user_inv[item]}."
    else:
        parts = ", ".join(f"×{count} **{item}**" for item, count in totals.items())
        msg = f"Added {parts} to {member.display_name}'s inventory."
    if sets > 0:
        msg += f" They have **{sets} complete set{'s' if sets != 1 else ''}**!"
    await interaction.response.send_message(msg, ephemeral=True)
