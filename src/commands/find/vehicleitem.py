"""Handler for /find vehicleitem."""

from __future__ import annotations

import discord

from src.commands.formatting import add_shops_field, truncate
from src.starcitizenwiki_api.vehicle_items import VehicleItem

from .shared import VEHICLE_ITEM_COLOR, handle_single


def build_vehicle_item_embed(item: VehicleItem) -> discord.Embed:
    title = f"{item.manufacturer} {item.name}" if item.manufacturer else item.name
    embed = discord.Embed(title=title, url=item.web_url or None, color=VEHICLE_ITEM_COLOR)

    if item.description:
        embed.description = truncate(item.description)

    if item.image_url:
        embed.set_thumbnail(url=item.image_url)

    item_type = " · ".join(part for part in (item.type, item.sub_type) if part)
    if item_type:
        embed.add_field(name="Type", value=item_type, inline=False)

    if item.size is not None or item.grade or item.classification:
        parts = []
        if item.size is not None:
            parts.append(f"S{item.size}")
        if item.grade:
            parts.append(item.grade)
        if item.classification:
            parts.append(item.classification)
        embed.add_field(name="Size / Grade", value=" · ".join(parts), inline=True)

    add_shops_field(embed, item.purchase_locations)
    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await handle_single(cog, interaction, name, "vehicle_items_api", build_vehicle_item_embed)
