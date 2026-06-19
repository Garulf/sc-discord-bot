"""The /shipweapon command and /find shipweapon subcommand handler."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.ship_weapons import ShipWeapon
from src.commands.formatting import add_shops_field, format_number as _format_number


def build_ship_weapon_embed(weapon: ShipWeapon) -> discord.Embed:
    title = f"{weapon.manufacturer} {weapon.name}" if weapon.manufacturer else weapon.name
    embed = discord.Embed(title=title, url=weapon.web_url or None, color=0x1B7BE0)

    if weapon.description:
        description = weapon.description.strip()
        embed.description = description[:500] + ("…" if len(description) > 500 else "")

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


class ShipWeaponsCog(commands.Cog):
    """Ship weapon component lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def ship_weapon_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await self.bot.ship_weapons_api.search(current, limit=25)
        except StarCitizenWikiError:
            return []
        results.sort(key=lambda w: len(w.name))
        seen: set[str] = set()
        choices: list[app_commands.Choice[str]] = []
        for weapon in results:
            if weapon.name in seen:
                continue
            seen.add(weapon.name)
            choices.append(app_commands.Choice(name=weapon.name[:100], value=weapon.name[:100]))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="shipweapon", description="Look up a ship-mounted weapon component")
    @app_commands.describe(name="Weapon name to search for (e.g. Laser Cannon, Gatling)")
    @app_commands.autocomplete(name=ship_weapon_autocomplete)
    async def shipweapon(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            weapon = await self.bot.ship_weapons_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(
                f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True
            )
            return
        if weapon is None:
            await interaction.followup.send(
                f"No ship weapon found matching **{name}**.", ephemeral=True
            )
            return
        await interaction.followup.send(embed=build_ship_weapon_embed(weapon))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShipWeaponsCog(bot))


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await cog._handle_single(interaction, name, "ship-weapon")
