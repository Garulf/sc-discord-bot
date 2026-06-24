from __future__ import annotations

import asyncio

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL
from src.commands.find.shared import MISSION_COLOR
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.missions import HaulingOrder, Mission

_WIKELO_FACTION = "Wikelo Emporium"


def format_amount(order: HaulingOrder) -> str:
    lo, hi = order.min_amount, order.max_amount
    if lo is not None and hi is not None:
        return f"×{lo}" if lo == hi else f"×{lo}–{hi}"
    if hi is not None:
        return f"up to ×{hi}"
    if lo is not None:
        return f"×{lo}+"
    return ""


def build_wikelo_embed(mission: Mission, image_url: str | None = None) -> discord.Embed:
    embed = discord.Embed(title=mission.title, url=mission.web_url, color=MISSION_COLOR)

    if image_url:
        embed.set_image(url=image_url)

    if mission.reward_items:
        lines = []
        for ri in mission.reward_items:
            label = f"[{ri.name}]({ri.web_url})" if ri.web_url else ri.name
            if ri.amount > 1:
                label += f" ×{ri.amount}"
            lines.append(label)
        embed.add_field(name="Reward", value="\n".join(lines), inline=False)

    if mission.hauling_orders:
        lines = []
        for order in mission.hauling_orders:
            amount = format_amount(order)
            lines.append(f"{order.name} {amount}".strip())
        embed.add_field(name="Hauling Orders", value="\n".join(lines), inline=False)

    if mission.reputation_gained:
        rep = mission.reputation_gained[0]
        embed.add_field(name="Reputation", value=f"+{rep.amount} {rep.faction}", inline=True)

    embed.set_footer(text="Source: star-citizen.wiki")
    return embed


async def _get_wikelo_missions(bot) -> list[Mission]:
    missions = await bot.missions_api.search(faction=_WIKELO_FACTION, page_size=200)
    details = await asyncio.gather(
        *[bot.missions_api.get(m.uuid) for m in missions],
        return_exceptions=True,
    )
    return [m for m in details if isinstance(m, Mission)]


async def _fetch_item_image(bot, link: str) -> str | None:
    try:
        payload = await bot.sc_client.get(link)
        images = (payload.get("data") or {}).get("images") or []
        if images and isinstance(images[0], dict):
            return images[0].get("thumbnail_url")
    except Exception:  # noqa: BLE001
        pass
    return None


async def autocomplete(cog, current: str) -> list[app_commands.Choice[str]]:
    try:
        missions = await _get_wikelo_missions(cog.bot)
    except Exception:  # noqa: BLE001
        return []
    seen: set[str] = set()
    choices: list[app_commands.Choice[str]] = []
    lowered = current.lower()
    for mission in missions:
        for ri in mission.reward_items:
            if ri.name in seen:
                continue
            if lowered and lowered not in ri.name.lower():
                continue
            seen.add(ri.name)
            choices.append(
                app_commands.Choice(
                    name=ri.name[:MAX_CHOICE_LABEL],
                    value=ri.name[:MAX_CHOICE_LABEL],
                )
            )
            if len(choices) >= MAX_AUTOCOMPLETE_CHOICES:
                return choices
    return choices


async def handle(cog, interaction: discord.Interaction, reward: str) -> None:
    await interaction.response.defer()
    try:
        missions = await _get_wikelo_missions(cog.bot)
    except StarCitizenWikiError as e:
        await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
        return

    mission = next(
        (m for m in missions if any(ri.name == reward for ri in m.reward_items)),
        None,
    )
    if mission is None:
        await interaction.followup.send(f"No Wikelo mission found rewarding **{reward}**.", ephemeral=True)
        return

    image_url: str | None = None
    if mission.reward_items and mission.reward_items[0].link:
        image_url = await _fetch_item_image(cog.bot, mission.reward_items[0].link)

    await interaction.followup.send(embed=build_wikelo_embed(mission, image_url))
