"""Handler for /inventory status everyone."""

from __future__ import annotations

import discord

from ..shared import build_status_table, get_guild_inventory


async def handle(cog, interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    await interaction.response.defer()
    guild_inv = await get_guild_inventory(cog, guild.id)
    active = {uid: inv for uid, inv in guild_inv.items() if inv}

    if not active:
        await interaction.followup.send("No inventory data found for this server.")
        return

    member_names: dict[str, str] = {}
    for user_key in active:
        member = guild.get_member(int(user_key))
        if member is None:
            try:
                member = await guild.fetch_member(int(user_key))
            except (discord.NotFound, discord.HTTPException):
                continue
        member_names[user_key] = member.display_name

    table = build_status_table(active, member_names)
    content = f"**DCHS Inventory Status**\n```\n{table}\n```" if table else "**DCHS Inventory Status**\n*No inventory data found.*"
    await interaction.followup.send(content)
