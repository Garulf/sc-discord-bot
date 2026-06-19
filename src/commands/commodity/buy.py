"""Handler for /commodity buy."""
from __future__ import annotations
from typing import Optional
import discord
from discord import app_commands


async def handle(
    cog,
    interaction: discord.Interaction,
    name: str,
    system: Optional[app_commands.Choice[str]] = None,
    place: Optional[app_commands.Choice[str]] = None,
    exterior_cargo: Optional[bool] = None,
) -> None:
    await cog._respond(interaction, name, selling=False, system=system, place=place, exterior_cargo=exterior_cargo)
