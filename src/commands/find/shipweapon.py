"""Handler for /find shipweapon."""

from __future__ import annotations

import discord

from src.commands.formatting import add_shops_field, truncate
from src.commands.formatting import format_number as _format_number
from src.starcitizenwiki_api.ship_weapons import ShipWeapon

from .shared import SHIP_WEAPON_COLOR, handle_single


def build_ship_weapon_embed(weapon: ShipWeapon) -> discord.Embed:
    title = f"{weapon.manufacturer} {weapon.name}" if weapon.manufacturer else weapon.name
    embed = discord.Embed(title=title, url=weapon.web_url or None, color=SHIP_WEAPON_COLOR)

    if weapon.description:
        embed.description = truncate(weapon.description)

    if weapon.image_url:
        embed.set_thumbnail(url=weapon.image_url)

    weapon_type = " · ".join(part for part in (weapon.type, weapon.sub_type) if part)
    if weapon_type:
        embed.add_field(name="Type", value=weapon_type, inline=False)

    if weapon.size is not None:
        size_str = f"S{weapon.size}"
        grade_class = " · ".join(part for part in (weapon.grade, weapon.classification) if part)
        embed.add_field(
            name="Size / Grade",
            value=f"{size_str} · {grade_class}" if grade_class else size_str,
            inline=True,
        )

    alpha = _format_number(weapon.alpha_damage)
    if alpha:
        dps = _format_number(weapon.dps)
        embed.add_field(
            name="Damage",
            value=f"{alpha} dmg" + (f" · {dps} DPS" if dps else ""),
            inline=True,
        )

    fire_rate = _format_number(weapon.fire_rate, " rpm")
    if fire_rate:
        embed.add_field(name="Fire Rate", value=fire_rate, inline=True)

    rng = _format_number(weapon.range, " m")
    if rng:
        embed.add_field(name="Range", value=rng, inline=True)

    speed = _format_number(weapon.speed, " m/s")
    if speed:
        embed.add_field(name="Projectile Speed", value=speed, inline=True)

    add_shops_field(embed, weapon.purchase_locations, fallback_text="No known in-game purchase locations.")
    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await handle_single(cog, interaction, name, "ship_weapons_api", build_ship_weapon_embed)
