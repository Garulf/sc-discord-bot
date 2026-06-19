"""The /clothes command and /find clothes subcommand handler."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.autocomplete import item_choices
from src.commands.formatting import add_shops_field, truncate
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.clothes import ClothingItem


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


class ClothesCog(commands.Cog):
    """Clothing lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def clothes_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await self.bot.clothes_api.search(current, limit=25)
        except StarCitizenWikiError:
            return []
        results.sort(key=lambda w: len(w.name))
        return item_choices(results)

    @app_commands.command(name="clothes", description="Look up Star Citizen clothing and where to buy it")
    @app_commands.describe(name="Clothing name to search for")
    @app_commands.autocomplete(name=clothes_autocomplete)
    async def clothes(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            item = await self.bot.clothes_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
            return
        if item is None:
            await interaction.followup.send(f"No clothing found matching **{name}**.", ephemeral=True)
            return
        await interaction.followup.send(embed=build_clothes_embed(item))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ClothesCog(bot))


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await cog._handle_single(interaction, name, "clothes")
