"""Handler for /find all — searches across all item categories at once."""

from __future__ import annotations

import discord

from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.client import NotFoundError

from .armor import build_armor_embed
from .clothes import build_clothes_embed
from .item import build_item_embed
from .shipweapon import build_ship_weapon_embed
from .vehicleitem import build_vehicle_item_embed
from .weapon import build_weapon_embed
from .weaponattachment import build_weapon_attachment_embed

DISPATCH: dict[str, tuple[str, object]] = {
    "weapon": ("weapons_api", build_weapon_embed),
    "ship-weapon": ("ship_weapons_api", build_ship_weapon_embed),
    "armor": ("armor_api", build_armor_embed),
    "clothes": ("clothes_api", build_clothes_embed),
    "vehicle-item": ("vehicle_items_api", build_vehicle_item_embed),
    "weapon-attachment": ("weapon_attachments_api", build_weapon_attachment_embed),
    "item": ("items_api", build_item_embed),
}


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await interaction.response.defer()
    category_key, _, identifier = name.partition(":")
    if not identifier:
        await interaction.followup.send("Please select a result from the autocomplete list.", ephemeral=True)
        return
    entry = DISPATCH.get(category_key)
    if entry is None:
        await interaction.followup.send(f"Unknown category **{category_key}**.", ephemeral=True)
        return
    api_attr, embed_builder = entry
    api = getattr(cog.bot, api_attr)
    try:
        try:
            item = await api.get(identifier)
        except NotFoundError:
            item = await api.find(identifier)
    except StarCitizenWikiError as e:
        await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
        return
    if item is None:
        await interaction.followup.send(f"No item found matching **{identifier}**.", ephemeral=True)
        return
    await interaction.followup.send(embed=embed_builder(item))
