"""Parsing, display, and cascading autocomplete for beacon locations."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from src.commands.autocomplete import name_choices

logger = logging.getLogger(__name__)

FLYABLE_SYSTEMS = ("Stanton", "Pyro", "Nyx")

_MAX_PARTS = 3
_SEPARATOR = " › "
_BODY_TYPES = {"Planet", "Moon"}


def parse_location(raw: str) -> tuple[str, ...] | None:
    parts = [p.strip() for p in raw.split(":")]
    if not parts or len(parts) > _MAX_PARTS or any(not p for p in parts):
        return None
    return tuple(parts)


def format_breadcrumb(raw: str) -> str:
    parts = parse_location(raw)
    return _SEPARATOR.join(parts) if parts else raw


def combine_location(system: str, planet: str | None, poi: str | None) -> str:
    return ":".join(part for part in (system, planet, poi) if part)


async def system_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    query = current.strip().lower()
    return name_choices(name for name in FLYABLE_SYSTEMS if query in name.lower())


async def _search_pois(interaction: discord.Interaction, query: str) -> list:
    try:
        return await interaction.client.locations_api.search(query)
    except Exception as error:  # noqa: BLE001 - autocomplete must never raise
        logger.warning("Location autocomplete search failed: %s", error)
        return []


def _namespace_value(interaction: discord.Interaction, name: str) -> str | None:
    value = getattr(interaction.namespace, name, None)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _matches(value: str | None, wanted: str | None) -> bool:
    return wanted is None or (value is not None and value.lower() == wanted.lower())


async def planet_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    system = _namespace_value(interaction, "system")
    results = await _search_pois(interaction, current)
    return name_choices(r.name for r in results if r.type in _BODY_TYPES and _matches(r.star_system_name, system))


async def poi_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    system = _namespace_value(interaction, "system")
    planet = _namespace_value(interaction, "planet")
    results = await _search_pois(interaction, current)
    return name_choices(
        r.name
        for r in results
        if r.type not in _BODY_TYPES and _matches(r.star_system_name, system) and _matches(r.parent_name, planet)
    )


async def route_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    results = await _search_pois(interaction, current)
    values: list[str] = []
    for r in results:
        if r.star_system_name not in FLYABLE_SYSTEMS:
            continue
        if r.parent_name and r.parent_name != r.star_system_name:
            values.append(f"{r.star_system_name}:{r.parent_name}:{r.name}")
        else:
            values.append(f"{r.star_system_name}:{r.name}")
    return name_choices(values)
