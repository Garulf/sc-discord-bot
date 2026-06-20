"""Handler for /find mission."""

from __future__ import annotations

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.client import NotFoundError
from src.starcitizenwiki_api.missions import Mission

_DESCRIPTION_MAX = 350


def build_mission_embed(mission: Mission) -> discord.Embed:
    embed = discord.Embed(title=mission.title, url=mission.web_url, color=0x5865F2)

    if mission.description:
        desc = mission.description
        if len(desc) > _DESCRIPTION_MAX:
            desc = desc[:_DESCRIPTION_MAX].rsplit(" ", 1)[0] + "…"
        embed.description = desc

    if mission.mission_giver:
        giver = mission.mission_giver
        if mission.faction_name and mission.faction_name != mission.mission_giver:
            giver = f"{mission.mission_giver} ({mission.faction_name})"
        embed.add_field(name="Mission Giver", value=giver, inline=True)

    if mission.mission_type:
        embed.add_field(name="Type", value=mission.mission_type, inline=True)

    legality = mission.legality_label or ("Illegal" if mission.illegal else "Legal")
    embed.add_field(name="Legality", value=legality, inline=True)

    if mission.rank_label is not None:
        embed.add_field(name="Required Rank", value=mission.rank_label, inline=True)

    reward_parts: list[str] = []
    if mission.reward_min:
        reward_parts.append(f"{mission.reward_min:,}")
    if mission.reward_max and mission.reward_max != mission.reward_min:
        reward_parts.append(f"{mission.reward_max:,}")
    if reward_parts:
        currency = mission.reward_currency or "UEC"
        embed.add_field(name="Reward", value=f"{' – '.join(reward_parts)} {currency}", inline=True)

    if mission.star_systems:
        embed.add_field(name="Star Systems", value=", ".join(mission.star_systems), inline=True)

    if mission.cooldown_label:
        embed.add_field(name="Cooldown", value=mission.cooldown_label, inline=True)

    if mission.time_to_complete_minutes is not None:
        embed.add_field(name="Time Limit", value=f"{mission.time_to_complete_minutes:g} min", inline=True)

    flags: list[str] = []
    if mission.shareable:
        flags.append("Shareable")
    if mission.has_combat:
        flags.append("Combat")
    if mission.has_prerequisites:
        flags.append("Has Prerequisites")
    if mission.once_only:
        flags.append("Once Only")
    if mission.max_players_per_instance and mission.max_players_per_instance > 1:
        flags.append(f"Up to {mission.max_players_per_instance} players")
    if flags:
        embed.add_field(name="Flags", value=" · ".join(flags), inline=False)

    if mission.blueprints:
        lines = [f"[{b.name}]({b.link})" for b in mission.blueprints]
        text = "\n".join(lines)
        if len(text) > 1024:
            visible = []
            total = 0
            for line in lines:
                if total + len(line) + 1 > 1000:
                    visible.append(f"… and {len(lines) - len(visible)} more")
                    break
                visible.append(line)
                total += len(line) + 1
            text = "\n".join(visible)
        embed.add_field(name="Unlocks Blueprints", value=text, inline=False)

    embed.set_footer(text="Source: star-citizen.wiki")
    return embed


async def autocomplete(cog, current: str) -> list[app_commands.Choice[str]]:
    try:
        results = await cog.bot.missions_api.search(current or None, limit=MAX_AUTOCOMPLETE_CHOICES)
    except Exception:  # noqa: BLE001
        return []
    return [
        app_commands.Choice(
            name=m.title[:MAX_CHOICE_LABEL],
            value=m.uuid[:MAX_CHOICE_LABEL],
        )
        for m in sorted(results, key=lambda m: len(m.title))
    ]


async def handle(cog, interaction: discord.Interaction, name: str) -> None:
    await interaction.response.defer()
    api = cog.bot.missions_api
    try:
        try:
            mission = await api.get(name)
        except NotFoundError:
            results = await api.search(name, limit=1)
            mission = results[0] if results else None
    except StarCitizenWikiError as e:
        await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
        return
    if mission is None:
        await interaction.followup.send(f"No mission found matching **{name}**.", ephemeral=True)
        return
    await interaction.followup.send(embed=build_mission_embed(mission))
