"""Handler for /find blueprint."""

from __future__ import annotations

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL
from src.commands.find.shared import BLUEPRINT_COLOR
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.blueprints import Blueprint
from src.starcitizenwiki_api.client import NotFoundError


def build_blueprint_embed(blueprint: Blueprint) -> discord.Embed:
    embed = discord.Embed(title=blueprint.name, url=blueprint.web_url, color=BLUEPRINT_COLOR)

    if blueprint.output_type_label:
        embed.description = blueprint.output_type_label

    if blueprint.craft_time_label:
        embed.add_field(name="Craft Time", value=blueprint.craft_time_label, inline=True)

    if blueprint.ingredients:

        def _format_ingredient(i) -> str:
            if i.quantity_scu is not None:
                line = f"× {i.quantity_scu:g} SCU  {i.name}"
            elif i.quantity is not None:
                line = f"× {i.quantity}  {i.name}"
            else:
                line = i.name
            if i.modifiers:
                line += f"\n  ↳ {', '.join(i.modifiers)}"
            return line

        lines = [_format_ingredient(i) for i in blueprint.ingredients]
        embed.add_field(name="Components", value="\n".join(lines), inline=False)

    if blueprint.unlocking_missions_grouped:
        groups = blueprint.unlocking_missions_grouped
        lines: list[str] = []
        multi_group = len(groups) > 1
        for group in groups:
            if multi_group:
                lines.append(f"**{group.label}**")
            for m in group.missions:
                if m.title.startswith("<=") and m.title.endswith("=>"):
                    continue
                label = f"[{m.title}]({m.web_url})" if m.web_url else m.title
                if m.count > 1:
                    label += f" ×{m.count}"
                lines.append(label)
        if lines:
            visible: list[str] = []
            total = 0
            for line in lines:
                if total + len(line) + 1 > 1000:
                    visible.append(f"… and {len(lines) - len(visible)} more")
                    break
                visible.append(line)
                total += len(line) + 1
            embed.add_field(name="Unlocked By", value="\n".join(visible), inline=False)

    embed.set_footer(text="Source: star-citizen.wiki")
    return embed


async def autocomplete(cog, current: str) -> list[app_commands.Choice[str]]:
    try:
        results = await cog.bot.blueprints_api.search(query=current or None, page_size=MAX_AUTOCOMPLETE_CHOICES)
    except Exception:  # noqa: BLE001
        return []
    return [
        app_commands.Choice(
            name=bp.name[:MAX_CHOICE_LABEL],
            value=bp.uuid[:MAX_CHOICE_LABEL],
        )
        for bp in sorted(results, key=lambda bp: len(bp.name))
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
