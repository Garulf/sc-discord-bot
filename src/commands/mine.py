"""The /mine command: look up where to mine a specific resource."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.autocomplete import item_choices
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.client import NotFoundError
from src.starcitizenwiki_api.mineables import Mineable, MiningLocation

MINE_COLOR = 0xF59E0B

_METHOD_LABELS = {
    "Ship": "⛏️ Ship",
    "Ground Vehicle": "🚜 ROC",
    "FPS": "💎 FPS",
    "Harvestable": "🌿 Harvestable",
}

_TYPE_LABELS = {
    "Asteroid": "Asteroid",
    "Asteroid_ValidQT": "Asteroid (QT)",
    "Moon": "Moon",
    "Planet": "Planet",
    "Outpost": None,
    "Settlement": None,
}

_MAX_LOCS_PER_SYSTEM = 5


def _loc_line(loc: MiningLocation) -> str:
    type_label = _TYPE_LABELS.get(loc.type)
    if type_label is None and loc.parent_name:
        context = loc.parent_name
    elif type_label:
        context = type_label
    else:
        context = loc.type

    prob = f" · {loc.probability_percent:.0f}%" if loc.probability_percent is not None else ""
    return f"{loc.display_name} ({context}){prob}"


def build_mine_embed(mineable: Mineable) -> discord.Embed:
    embed = discord.Embed(title=mineable.name, url=mineable.web_url, color=MINE_COLOR)

    if mineable.image_url:
        embed.set_thumbnail(url=mineable.image_url)

    if mineable.methods:
        method_str = " · ".join(_METHOD_LABELS.get(m, m) for m in mineable.methods)
        embed.description = f"**Mining method:** {method_str}"

    for sg in mineable.systems_grouped:
        locs = sorted(sg.locations, key=lambda x: x.probability_percent or 0, reverse=True)
        shown = locs[:_MAX_LOCS_PER_SYSTEM]
        lines = [_loc_line(loc) for loc in shown]
        extra = len(locs) - _MAX_LOCS_PER_SYSTEM
        if extra > 0:
            lines.append(f"*…and {extra} more*")
        embed.add_field(name=sg.name, value="\n".join(lines) or "No locations found.", inline=False)

    if not mineable.systems_grouped:
        embed.add_field(name="Locations", value="No location data available.", inline=False)

    embed.set_footer(text="Source: star-citizen.wiki")
    return embed


class MineCog(commands.Cog):
    """Where to mine a specific resource."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="mine", description="Where to mine a resource in Star Citizen")
    @app_commands.describe(mineable="The resource to mine")
    async def mine(self, interaction: discord.Interaction, mineable: str) -> None:
        await interaction.response.defer()
        try:
            item = await self.bot.mineables_api.get(mineable)
        except NotFoundError:
            await interaction.followup.send(f"No mineable found for **{mineable}**.", ephemeral=True)
            return
        except StarCitizenWikiError as exc:
            await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API: {exc}", ephemeral=True)
            return
        await interaction.followup.send(embed=build_mine_embed(item))

    @mine.autocomplete("mineable")
    async def mine_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        try:
            results = await self.bot.mineables_api.search(current)
        except Exception:  # noqa: BLE001
            return []
        return item_choices(results, use_slug=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MineCog(bot))
