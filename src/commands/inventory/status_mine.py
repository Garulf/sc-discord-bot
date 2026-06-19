"""Handler for /inventory status mine."""
from __future__ import annotations
import discord
from .helpers import complete_sets, embed_color, format_mine


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    guild_inv = await cog._get_guild_inventory(interaction.guild_id)
    user_inv = guild_inv.get(str(interaction.user.id), {})
    sets = complete_sets(user_inv)

    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s DCHS Inventory",
        description=format_mine(user_inv) if user_inv else "*Your inventory is empty.*",
        color=embed_color(user_inv),
    )
    embed.add_field(name="Complete Sets", value=str(sets) if sets else "None", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)
