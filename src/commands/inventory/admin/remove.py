"""Handler for /inventory admin remove."""

from __future__ import annotations

import discord

from ..shared import get_guild_inventory, save_guild_inventory
from ..subscriptions import refresh_live_status


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
        totals[item] = totals.get(item, 0) + count

    for item, count in totals.items():
        have = user_inv.get(item, 0)
        if have < count:
            await interaction.response.send_message(
                f"{member.display_name} only has ×{have} **{item}** but tried to remove ×{count}.", ephemeral=True
            )
            return

    removed_parts = []
    for item, count in totals.items():
        user_inv[item] = user_inv[item] - count
        if user_inv[item] == 0:
            del user_inv[item]
        removed_parts.append((item, count, user_inv.get(item, 0)))

    guild_inv[user_key] = user_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    if len(removed_parts) == 1:
        item, count, remaining = removed_parts[0]
        msg = f"Removed ×{count} **{item}** from {member.display_name}'s inventory. They now have ×{remaining}."
    else:
        parts = ", ".join(f"×{count} **{item}**" for item, count, _ in removed_parts)
        msg = f"Removed {parts} from {member.display_name}'s inventory."
    await interaction.response.send_message(msg, ephemeral=True)
    await refresh_live_status(cog, interaction.guild_id)
