"""Handler for /find weapon."""

from __future__ import annotations

import discord

from src.commands.formatting import add_shops_field, truncate
from src.commands.formatting import format_number as _format_number
from src.starcitizenwiki_api import Weapon

from .shared import handle_single, WEAPON_COLOR


def build_weapon_embed(weapon: Weapon) -> discord.Embed:
    title = f"{weapon.manufacturer} {weapon.name}" if weapon.manufacturer else weapon.name
    embed = discord.Embed(title=title, url=weapon.web_url or None, color=WEAPON_COLOR)

    if weapon.description:
        embed.description = truncate(weapon.description)

    if weapon.image_url:
        embed.set_thumbnail(url=weapon.image_url)

    classification = " · ".join(part for part in (weapon.classification, weapon.weapon_type) if part)
    if classification:
        embed.add_field(name="Type", value=classification, inline=False)

    if weapon.fire_mode:
        embed.add_field(name="Fire Mode", value=weapon.fire_mode, inline=True)

    if weapon.magazine_size is not None:
        embed.add_field(name="Magazine", value=str(weapon.magazine_size), inline=True)

    rpm = _format_number(weapon.rpm, " rpm")
    if rpm:
        embed.add_field(name="Rate of Fire", value=rpm, inline=True)

    alpha = _format_number(weapon.alpha_damage)
    if alpha:
        dps = _format_number(weapon.dps)
        value = f"{alpha} dmg" + (f" · {dps} DPS" if dps else "")
        embed.add_field(name="Damage", value=value, inline=True)

    rng = _format_number(weapon.effective_range, " m")
    if rng:
        embed.add_field(name="Effective Range", value=rng, inline=True)

    if weapon.ammunition_type:
        embed.add_field(name="Ammo", value=weapon.ammunition_type, inline=True)

    add_shops_field(embed, weapon.purchase_locations, fallback_text="No known in-game purchase locations.")
    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await handle_single(cog, interaction, name, "weapons_api", build_weapon_embed)
