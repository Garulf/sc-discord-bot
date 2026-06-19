"""Handler for /commodity buy."""

from __future__ import annotations

import discord
from discord import app_commands


async def handle(
    cog,
    interaction: discord.Interaction,
    name: str,
    system: app_commands.Choice[str] | None = None,
    place: app_commands.Choice[str] | None = None,
    exterior_cargo: bool | None = None,
) -> None:
    await cog._respond(interaction, name, selling=False, system=system, place=place, exterior_cargo=exterior_cargo)
