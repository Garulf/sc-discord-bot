"""Handler for /find clothes."""

from __future__ import annotations

import discord

from src.commands.formatting import add_shops_field, truncate
from src.starcitizenwiki_api.clothes import ClothingItem

from .shared import handle_single


def build_clothes_embed(item: ClothingItem) -> discord.Embed:
    title = f"{item.manufacturer} {item.name}" if item.manufacturer else item.name
    embed = discord.Embed(title=title, url=item.web_url or None, color=0xA855F7)

    if item.description:
        embed.description = truncate(item.description)

    if item.image_url:
        embed.set_thumbnail(url=item.image_url)

    item_type = " · ".join(part for part in (item.type, item.sub_type) if part)
    if item_type:
        embed.add_field(name="Type", value=item_type, inline=False)

    add_shops_field(embed, item.purchase_locations)
    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await handle_single(cog, interaction, name, "clothes_api", build_clothes_embed)
