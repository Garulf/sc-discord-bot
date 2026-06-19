"""Shared code for the /find command group.

Contains the single-item lookup used by every per-category subcommand and all
autocomplete callbacks. Embed builders live in the individual subcommand files
alongside their handlers.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL, item_choices
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.client import NotFoundError

CATEGORIES = [
    ("weapon", "Weapon"),
    ("ship-weapon", "Ship Weapon"),
    ("armor", "Armor"),
    ("clothes", "Clothing"),
    ("vehicle-item", "Vehicle Item"),
    ("weapon-attachment", "Weapon Attachment"),
    ("item", "Item"),
    ("mission", "Mission"),
]

API_ATTRS = [
    "weapons_api",
    "ship_weapons_api",
    "armor_api",
    "clothes_api",
    "vehicle_items_api",
    "weapon_attachments_api",
    "items_api",
    "missions_api",
]


async def handle_single(
    cog,
    interaction: discord.Interaction,
    name: str,
    api_attr: str,
    embed_builder: Callable[[Any], discord.Embed],
) -> None:
    await interaction.response.defer()
    api = getattr(cog.bot, api_attr)
    try:
        try:
            item = await api.get(name)
        except NotFoundError:
            item = await api.find(name)
    except StarCitizenWikiError as e:
        await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
        return
    if item is None:
        await interaction.followup.send(f"No item found matching **{name}**.", ephemeral=True)
        return
    await interaction.followup.send(embed=embed_builder(item))


async def autocomplete_single(cog, api_attr: str, current: str) -> list[app_commands.Choice[str]]:
    try:
        results = await getattr(cog.bot, api_attr).search(current, limit=25)
    except Exception:  # noqa: BLE001 - autocomplete failures are silently dropped
        return []
    return item_choices(sorted(results, key=lambda x: len(x.name)), use_slug=True)


async def autocomplete_all(cog, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete across all categories; choice value is ``category_key:slug``."""
    results = await asyncio.gather(
        *[getattr(cog.bot, attr).search(current, limit=5) for attr in API_ATTRS],
        return_exceptions=True,
    )
    choices: list[app_commands.Choice[str]] = []
    global_seen: set[str] = set()
    for (category_key, category_label), result in zip(CATEGORIES, results):
        if isinstance(result, Exception):
            continue
        for item in sorted(result, key=lambda x: len(x.name)):
            if item.name in global_seen:
                continue
            global_seen.add(item.name)
            identifier = item.slug or item.name
            choices.append(
                app_commands.Choice(
                    name=f"{item.name} ({category_label})"[:MAX_CHOICE_LABEL],
                    value=f"{category_key}:{identifier}"[:MAX_CHOICE_LABEL],
                )
            )
            if len(choices) >= MAX_AUTOCOMPLETE_CHOICES:
                return choices
    return choices
