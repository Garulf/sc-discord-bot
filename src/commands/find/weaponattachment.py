"""Handler for /find weaponattachment."""

from __future__ import annotations

import discord

from src.commands.formatting import add_shops_field, truncate
from src.starcitizenwiki_api.weapon_attachments import WeaponAttachment

from .shared import handle_single


def build_weapon_attachment_embed(item: WeaponAttachment) -> discord.Embed:
    title = f"{item.manufacturer} {item.name}" if item.manufacturer else item.name
    embed = discord.Embed(title=title, url=item.web_url or None, color=0xF59E0B)

    if item.description:
        embed.description = truncate(item.description)

    if item.image_url:
        embed.set_thumbnail(url=item.image_url)

    item_type = " · ".join(part for part in (item.type, item.sub_type) if part)
    if item_type:
        embed.add_field(name="Type", value=item_type, inline=False)

    if item.size is not None or item.grade:
        parts = []
        if item.size is not None:
            parts.append(f"S{item.size}")
        if item.grade:
            parts.append(item.grade)
        embed.add_field(name="Size / Grade", value=" · ".join(parts), inline=True)

    add_shops_field(embed, item.purchase_locations)
    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await handle_single(cog, interaction, name, "weapon_attachments_api", build_weapon_attachment_embed)
