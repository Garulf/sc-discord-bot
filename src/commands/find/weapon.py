"""The /weapon command and /find weapon subcommand handler."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.autocomplete import item_choices
from src.commands.formatting import add_shops_field, truncate
from src.commands.formatting import format_number as _format_number
from src.starcitizenwiki_api import StarCitizenWikiError, Weapon


def build_weapon_embed(weapon: Weapon) -> discord.Embed:
    title = f"{weapon.manufacturer} {weapon.name}" if weapon.manufacturer else weapon.name
    embed = discord.Embed(title=title, url=weapon.web_url or None, color=0xE07B1B)

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


class WeaponsCog(commands.Cog):
    """FPS / personal weapon lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def weapon_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await self.bot.weapons_api.search(current, limit=25)
        except StarCitizenWikiError:
            return []
        results.sort(key=lambda w: len(w.name))
        return item_choices(results)

    @app_commands.command(name="weapon", description="Look up Star Citizen FPS weapon info and where to buy it")
    @app_commands.describe(name="Weapon name to search for (e.g. P4-AR, Arrowhead)")
    @app_commands.autocomplete(name=weapon_autocomplete)
    async def weapon(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            weapon = await self.bot.weapons_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
            return
        if weapon is None:
            await interaction.followup.send(f"No weapon found matching **{name}**.", ephemeral=True)
            return
        await interaction.followup.send(embed=build_weapon_embed(weapon))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WeaponsCog(bot))


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await cog._handle_single(interaction, name, "weapon")
