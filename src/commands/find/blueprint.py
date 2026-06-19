"""Handler for /find blueprint."""

from __future__ import annotations

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.blueprints import Blueprint
from src.starcitizenwiki_api.client import NotFoundError


def build_blueprint_embed(blueprint: Blueprint) -> discord.Embed:
    embed = discord.Embed(title=blueprint.name, color=0xF97316)

    if blueprint.craft_time_seconds is not None:
        minutes, seconds = divmod(blueprint.craft_time_seconds, 60)
        time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
        embed.add_field(name="Craft Time", value=time_str, inline=True)

    if blueprint.ingredient_count is not None:
        embed.add_field(name="Ingredients", value=str(blueprint.ingredient_count), inline=True)

    if blueprint.is_default is not None:
        embed.add_field(name="Default", value="Yes" if blueprint.is_default else "No", inline=True)

    if blueprint.ingredients:
        lines = [
            f"× {i.quantity or '?'}  {i.name}"
            for i in blueprint.ingredients
        ]
        embed.add_field(name="Components", value="\n".join(lines), inline=False)

    if blueprint.description:
        embed.description = blueprint.description

    embed.set_footer(text="Source: star-citizen.wiki")
    return embed


async def autocomplete(cog, current: str) -> list[app_commands.Choice[str]]:
    if not current:
        return []
    try:
        results = await cog.bot.blueprints_api.search(query=current, page_size=MAX_AUTOCOMPLETE_CHOICES)
    except Exception:  # noqa: BLE001
        return []
    return [
        app_commands.Choice(
            name=bp.name[:MAX_CHOICE_LABEL],
            value=bp.uuid[:MAX_CHOICE_LABEL],
        )
        for bp in results
    ]


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await interaction.response.defer()
    api = cog.bot.blueprints_api
    try:
        try:
            item = await api.get(name)
        except NotFoundError:
            results = await api.search(query=name)
            item = results[0] if results else None
    except StarCitizenWikiError as e:
        await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
        return
    if item is None:
        await interaction.followup.send(f"No blueprint found matching **{name}**.", ephemeral=True)
        return
    await interaction.followup.send(embed=build_blueprint_embed(item))
