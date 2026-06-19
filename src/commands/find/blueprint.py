"""Handler for /find blueprint."""

from __future__ import annotations

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.blueprints import Blueprint
from src.starcitizenwiki_api.client import NotFoundError


def build_blueprint_embed(blueprint: Blueprint) -> discord.Embed:
    embed = discord.Embed(title=blueprint.name, url=blueprint.web_url, color=0xF97316)

    if blueprint.output_type_label:
        embed.description = blueprint.output_type_label

    if blueprint.craft_time_label:
        embed.add_field(name="Craft Time", value=blueprint.craft_time_label, inline=True)

    if blueprint.ingredients:
        def _format_ingredient(i) -> str:
            if i.quantity_scu is not None:
                line = f"× {i.quantity_scu:g} SCU  {i.name}"
            elif i.quantity is not None:
                line = f"x{i.quantity}  {i.name}"
            else:
                line = i.name
            if i.modifiers:
                line += f"\n  ↳ {', '.join(i.modifiers)}"
            return line

        lines = [_format_ingredient(i) for i in blueprint.ingredients]
        embed.add_field(name="Components", value="\n".join(lines), inline=False)

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
