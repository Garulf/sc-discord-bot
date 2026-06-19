"""Handler for /inventory admin clear."""
from __future__ import annotations
import discord
from discord import app_commands
from src.commands.checks import admin_or_sc_bot


async def handle(cog, interaction: discord.Interaction, member: discord.Member) -> None:
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

    guild_inv = await cog._get_guild_inventory(interaction.guild_id)
    user_key = str(member.id)
    if not guild_inv.get(user_key):
        await interaction.response.send_message(
            f"{member.display_name}'s inventory is already empty.", ephemeral=True
        )
        return

    guild_inv.pop(user_key, None)
    await cog._save_guild_inventory(interaction.guild_id, guild_inv)
    await interaction.response.send_message(
        f"{member.display_name}'s inventory has been cleared.", ephemeral=True
    )
