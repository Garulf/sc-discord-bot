"""The /item command and /find item subcommand handler."""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.items import Item
from src.commands.formatting import add_shops_field, format_number as _format_number


def build_item_embed(item: Item) -> discord.Embed:
    title = f"{item.manufacturer} {item.name}" if item.manufacturer else item.name
    embed = discord.Embed(title=title, url=item.web_url or None, color=0x6B7280)

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

    add_shops_field(embed, item.purchase_locations)
    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


class ItemsCog(commands.Cog):
    """Miscellaneous item lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def item_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await self.bot.items_api.search(current, limit=25)
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

    @app_commands.command(name="item", description="Look up a Star Citizen item and where to buy it")
    @app_commands.describe(name="Item name to search for")
    @app_commands.autocomplete(name=item_autocomplete)
    async def item(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            item = await self.bot.items_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(
                f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True
            )
            return
        if item is None:
            await interaction.followup.send(f"No item found matching **{name}**.", ephemeral=True)
            return
        await interaction.followup.send(embed=build_item_embed(item))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ItemsCog(bot))


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await cog._handle_single(interaction, name, "item")
