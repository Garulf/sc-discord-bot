"""Handler for /inventory admin remove."""

from __future__ import annotations

import discord
from discord import app_commands

from src.commands.checks import admin_or_sc_bot

from .helpers import ITEMS


async def handle(cog, interaction: discord.Interaction, member: discord.Member, item: str, count: int = 1) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    try:
        await admin_or_sc_bot(interaction)
    except app_commands.CheckFailure as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return
    if item not in ITEMS:
        await interaction.response.send_message(f"**{item}** is not a valid DCHS item.", ephemeral=True)
        return
    if count < 1:
        await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
        return

    guild_inv = await cog._get_guild_inventory(interaction.guild_id)
    user_key = str(member.id)
    user_inv = dict(guild_inv.get(user_key, {}))
    current_count = user_inv.get(item, 0)
    if current_count <= 0:
        await interaction.response.send_message(
            f"{member.display_name} doesn't have **{item}** in their inventory.", ephemeral=True
        )
        return

    removed = min(count, current_count)
    user_inv[item] = current_count - removed
    if user_inv[item] == 0:
        del user_inv[item]
    guild_inv[user_key] = user_inv
    await cog._save_guild_inventory(interaction.guild_id, guild_inv)

    remaining = user_inv.get(item, 0)
    await interaction.response.send_message(
        f"Removed ×{removed} **{item}** from {member.display_name}'s inventory. They now have ×{remaining}.",
        ephemeral=True,
    )
