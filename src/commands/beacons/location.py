"""Parsing, display, and autocomplete for beacon locations."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from src.commands.autocomplete import name_choices

logger = logging.getLogger(__name__)

FLYABLE_SYSTEMS = ("Stanton", "Pyro", "Nyx")

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


async def _search_pois(interaction: discord.Interaction, query: str) -> list:
    try:
        return await interaction.client.locations_api.search(query)
    except Exception as error:  # noqa: BLE001 - autocomplete must never raise
        logger.warning("Location autocomplete search failed: %s", error)
        return []


async def location_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    query = current.strip().lower()
    values = [name for name in FLYABLE_SYSTEMS if query in name.lower()]
    for poi in await _search_pois(interaction, current):
        if poi.star_system_name not in FLYABLE_SYSTEMS:
            continue
        if poi.parent_name and poi.parent_name != poi.star_system_name:
            values.append(f"{poi.star_system_name}:{poi.parent_name}:{poi.name}")
        else:
            values.append(f"{poi.star_system_name}:{poi.name}")
    return name_choices(values)
