from __future__ import annotations

import asyncio

import discord
from discord import app_commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL
from src.commands.find.shared import MISSION_COLOR
from src.http_cache import TTLCache
from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api._common import first_image
from src.starcitizenwiki_api.missions import HaulingOrder, Mission

_WIKELO_FACTION = "Wikelo Emporium"
_missions_cache: TTLCache = TTLCache()


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
        text = "\n".join(lines)
        if len(text) > 1024:
            visible: list[str] = []
            total = 0
            for line in lines:
                if total + len(line) + 1 > 1000:
                    visible.append(f"… and {len(lines) - len(visible)} more")
                    break
                visible.append(line)
                total += len(line) + 1
            text = "\n".join(visible)
        embed.add_field(name="Hauling Orders", value=text, inline=False)

    if mission.reputation_gained:
        rep = mission.reputation_gained[0]
        if rep.amount is not None:
            embed.add_field(name="Reputation", value=f"+{rep.amount} {rep.faction}", inline=True)

    embed.set_footer(text="Source: star-citizen.wiki")
    return embed


async def _get_wikelo_missions(bot) -> list[Mission]:
    cached = await _missions_cache.get("wikelo_missions")
    if cached is not None:
        return cached
    async with _missions_cache.lock("wikelo_missions"):
        cached = await _missions_cache.get("wikelo_missions")
        if cached is not None:
            return cached
        missions = await bot.missions_api.search(faction=_WIKELO_FACTION, page_size=200)
        details = await asyncio.gather(
            *[bot.missions_api.get(m.uuid) for m in missions],
            return_exceptions=True,
        )
        result = [m for m in details if isinstance(m, Mission)]
        await _missions_cache.set("wikelo_missions", result)
        return result


async def _fetch_item_image(bot, link: str) -> str | None:
    try:
        payload = await bot.sc_client.get(link)
        data = (payload.get("data") or {})
        return first_image(data.get("images"))
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
        (m for m in missions if any(ri.name[:MAX_CHOICE_LABEL] == reward for ri in m.reward_items)),
        None,
    )
    if mission is None:
        await interaction.followup.send(f"No Wikelo mission found rewarding **{reward}**.", ephemeral=True)
        return

    matched_reward = next(
        (ri for ri in mission.reward_items if ri.name[:MAX_CHOICE_LABEL] == reward),
        mission.reward_items[0],
    )
    image_url: str | None = None
    if matched_reward.link:
        image_url = await _fetch_item_image(cog.bot, matched_reward.link)

    await interaction.followup.send(embed=build_wikelo_embed(mission, image_url))
