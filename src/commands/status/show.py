"""Handler for /status show."""

from __future__ import annotations

import discord

from src.rsi_status import fetch_status_overview

from .shared import build_overview_embed, latest_incident


async def handle(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    try:
        overview = await fetch_status_overview()
    except Exception as e:  # noqa: BLE001 - surface a friendly message
        await interaction.followup.send(f"Couldn't reach the RSI status page right now: {e}", ephemeral=True)
        return
    incident = await latest_incident(cog, overview)
    await interaction.followup.send(embed=build_overview_embed(overview, incident=incident))
