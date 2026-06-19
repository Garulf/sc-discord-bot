"""Handler for /hangar status."""

from __future__ import annotations

import discord

from .embed import build_embed


async def handle(cog, interaction: discord.Interaction) -> None:
    if cog.schedule is None:
        await interaction.response.send_message(
            "Hangar state hasn't been set yet. Use `/hangar set` first.", ephemeral=True
        )
        return
    await interaction.response.send_message(embed=build_embed(cog.schedule, set_at=cog.set_at), ephemeral=True)
