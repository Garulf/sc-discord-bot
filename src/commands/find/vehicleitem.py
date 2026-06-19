"""The /vehicleitem command and /find vehicleitem subcommand handler."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.formatting import add_shops_field
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.vehicle_items import VehicleItem


def build_vehicle_item_embed(item: VehicleItem) -> discord.Embed:
    title = f"{item.manufacturer} {item.name}" if item.manufacturer else item.name
    embed = discord.Embed(title=title, url=item.web_url or None, color=0x22C55E)

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


class VehicleItemsCog(commands.Cog):
    """Vehicle item component lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def vehicle_item_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await self.bot.vehicle_items_api.search(current, limit=25)
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

    @app_commands.command(name="vehicleitem", description="Look up a Star Citizen vehicle item component")
    @app_commands.describe(name="Vehicle item name to search for")
    @app_commands.autocomplete(name=vehicle_item_autocomplete)
    async def vehicleitem(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            item = await self.bot.vehicle_items_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
            return
        if item is None:
            await interaction.followup.send(f"No vehicle item found matching **{name}**.", ephemeral=True)
            return
        await interaction.followup.send(embed=build_vehicle_item_embed(item))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VehicleItemsCog(bot))


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await cog._handle_single(interaction, name, "vehicle-item")
