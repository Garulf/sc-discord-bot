"""Parsing, display, and autocomplete for system:planet:location strings."""

from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands

from src.commands.autocomplete import name_choices

logger = logging.getLogger(__name__)

_MAX_PARTS = 3
_SEPARATOR = " › "


def parse_location(raw: str) -> tuple[str, ...] | None:
    parts = [p.strip() for p in raw.split(":")]
    if not parts or len(parts) > _MAX_PARTS or any(not p for p in parts):
        return None
    return tuple(parts)


def format_breadcrumb(raw: str) -> str:
    parts = parse_location(raw)
    return _SEPARATOR.join(parts) if parts else raw


async def location_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    query = current.rsplit(":", 1)[-1].strip()
    client = interaction.client
    results = await asyncio.gather(
        client.starsystems_api.search(query),
        client.celestial_objects_api.search(query),
        client.locations_api.search(query),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Location autocomplete search failed: %s", result)
    systems, bodies, pois = (r if isinstance(r, list) else [] for r in results)

    values: list[str] = []
    for system in systems:
        values.append(system.name)
    for body in bodies:
        if body.star_system_name:
            values.append(f"{body.star_system_name}:{body.name}")
    for poi in pois:
        if poi.star_system_name and poi.parent_name:
            values.append(f"{poi.star_system_name}:{poi.parent_name}:{poi.name}")
        elif poi.star_system_name:
            values.append(f"{poi.star_system_name}:{poi.name}")
    return name_choices(values)
