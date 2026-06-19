"""The /armor command and /find armor subcommand handler."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.formatting import add_shops_field
from src.commands.formatting import format_number as _format_number
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.armor import ArmorItem


def build_armor_embed(item: ArmorItem) -> discord.Embed:
    title = f"{item.manufacturer} {item.name}" if item.manufacturer else item.name
    embed = discord.Embed(title=title, url=item.web_url or None, color=0x4A90D9)

    if item.description:
        description = item.description.strip()
        embed.description = description[:500] + ("…" if len(description) > 500 else "")

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

    dr = _format_number(item.damage_reduction)
    if dr is not None:
        embed.add_field(name="Damage Reduction", value=f"{dr}%", inline=True)

    cap = _format_number(item.capacity)
    if cap is not None:
        embed.add_field(name="Capacity", value=cap, inline=True)

    add_shops_field(embed, item.purchase_locations)
    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


class ArmorCog(commands.Cog):
    """Armor lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def armor_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await self.bot.armor_api.search(current, limit=25)
        except StarCitizenWikiError:
            return []
        results.sort(key=lambda w: len(w.name))
        seen: set[str] = set()
        choices: list[app_commands.Choice[str]] = []
        for item in results:
            if item.name in seen:
                continue
            seen.add(item.name)
            choices.append(app_commands.Choice(name=item.name[:100], value=item.name[:100]))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="armor", description="Look up Star Citizen armor and where to buy it")
    @app_commands.describe(name="Armor name to search for")
    @app_commands.autocomplete(name=armor_autocomplete)
    async def armor(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            item = await self.bot.armor_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
            return
        if item is None:
            await interaction.followup.send(f"No armor found matching **{name}**.", ephemeral=True)
            return
        await interaction.followup.send(embed=build_armor_embed(item))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ArmorCog(bot))


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await cog._handle_single(interaction, name, "armor")
