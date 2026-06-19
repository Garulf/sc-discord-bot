"""Handler for /inventory admin clear-all."""

from __future__ import annotations

import discord
from discord import app_commands

from src.commands.checks import admin_or_sc_bot

from ..shared import save_guild_inventory


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    try:
        await admin_or_sc_bot(interaction)
    except app_commands.CheckFailure as e:
        await interaction.response.send_message(str(e), ephemeral=True)
        return

    await save_guild_inventory(cog, interaction.guild_id, {})
    await interaction.response.send_message("All inventories have been cleared.", ephemeral=True)
