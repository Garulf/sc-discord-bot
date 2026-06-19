"""Handler for /inventory admin add."""
from __future__ import annotations
import discord
from discord import app_commands
from src.commands.checks import admin_or_sc_bot
from .helpers import ITEMS, complete_sets


async def handle(
    cog, interaction: discord.Interaction, member: discord.Member, item: str, count: int = 1
) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return
    try:
        await admin_or_sc_bot(interaction)
    except app_commands.CheckFailure as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return
    if item not in ITEMS:
        await interaction.response.send_message(
            f"**{item}** is not a valid DCHS item. Choose from DCHS-01 through DCHS-07.",
            ephemeral=True,
        )
        return
    if count < 1:
        await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
        return

    guild_inv = await cog._get_guild_inventory(interaction.guild_id)
    user_key = str(member.id)
    user_inv = dict(guild_inv.get(user_key, {}))
    user_inv[item] = user_inv.get(item, 0) + count
    guild_inv[user_key] = user_inv
    await cog._save_guild_inventory(interaction.guild_id, guild_inv)

    total = user_inv[item]
    sets = complete_sets(user_inv)
    msg = f"Added ×{count} **{item}** to {member.display_name}'s inventory. They now have ×{total}."
    if sets > 0:
        msg += f" They have **{sets} complete set{'s' if sets != 1 else ''}**!"
    await interaction.response.send_message(msg, ephemeral=True)
