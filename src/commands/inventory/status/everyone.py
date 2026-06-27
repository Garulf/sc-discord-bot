"""Handler for /inventory status everyone."""

from __future__ import annotations

import discord

from ..shared import MAX_EMBED_FIELDS, complete_sets, format_field, get_guild_inventory


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

    pooled: dict[str, int] = {}
    for inv in active.values():
        for item, count in inv.items():
            pooled[item] = pooled.get(item, 0) + count
    total_sets = complete_sets(pooled)
    embed = discord.Embed(
        title="DCHS Inventory Status",
        color=0x57F287 if total_sets > 0 else 0x5865F2,
    )
    embed.set_footer(text=f"Server total: {total_sets} complete set{'s' if total_sets != 1 else ''}")

    shown = 0
    for user_key, user_inv in sorted(active.items(), key=lambda kv: complete_sets(kv[1]), reverse=True):
        if shown >= MAX_EMBED_FIELDS:
            break
        member = guild.get_member(int(user_key))
        if member is None:
            try:
                member = await guild.fetch_member(int(user_key))
            except (discord.NotFound, discord.HTTPException):
                continue
        embed.add_field(name=member.display_name, value=format_field(user_inv), inline=True)
        shown += 1

    await interaction.followup.send(embed=embed)
