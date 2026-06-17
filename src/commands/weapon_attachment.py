from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.weapon_attachments import WeaponAttachment
from src.starcitizenwiki_api.weapons import PurchaseLocation


MAX_SHOPS_SHOWN = 8


def _format_number(value: Optional[float], suffix: str = "") -> Optional[str]:
    if value is None:
        return None
    rounded = round(value, 2)
    if rounded == int(rounded):
        rounded = int(rounded)
    return f"{rounded:,}{suffix}"


def _format_shop(shop: PurchaseLocation) -> str:
    price = _format_number(shop.price_buy, " aUEC") if shop.price_buy else "price n/a"
    place = " · ".join(part for part in (shop.location_name, shop.star_system) if part)
    terminal = shop.terminal_name or "Unknown terminal"
    suffix = f" ({place})" if place else ""
    return f"**{price}** — {terminal}{suffix}"


def build_weapon_attachment_embed(item: WeaponAttachment) -> discord.Embed:
    title = f"{item.manufacturer} {item.name}" if item.manufacturer else item.name
    embed = discord.Embed(title=title, url=item.web_url or None, color=0xF59E0B)

    if item.description:
        description = item.description.strip()
        embed.description = description[:500] + ("…" if len(description) > 500 else "")

    if item.image_url:
        embed.set_thumbnail(url=item.image_url)

    item_type = " · ".join(part for part in (item.type, item.sub_type) if part)
    if item_type:
        embed.add_field(name="Type", value=item_type, inline=False)

    if item.size is not None or item.grade:
        parts = []
        if item.size is not None:
            parts.append(f"S{item.size}")
        if item.grade:
            parts.append(item.grade)
        embed.add_field(name="Size / Grade", value=" · ".join(parts), inline=True)

    shops = [s for s in item.purchase_locations if s.price_buy is not None]
    if shops:
        shops.sort(key=lambda s: s.price_buy or float("inf"))
        lines = [_format_shop(s) for s in shops[:MAX_SHOPS_SHOWN]]
        remaining = len(shops) - MAX_SHOPS_SHOWN
        if remaining > 0:
            lines.append(f"…and {remaining} more location(s)")
        embed.add_field(name="Where to Buy", value="\n".join(lines), inline=False)

    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


class WeaponAttachmentsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def weapon_attachment_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await self.bot.weapon_attachments_api.search(current, limit=25)
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

    @app_commands.command(name="weaponattachment", description="Look up a Star Citizen weapon attachment")
    @app_commands.describe(name="Weapon attachment name to search for")
    @app_commands.autocomplete(name=weapon_attachment_autocomplete)
    async def weaponattachment(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            item = await self.bot.weapon_attachments_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(
                f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True
            )
            return
        if item is None:
            await interaction.followup.send(
                f"No weapon attachment found matching **{name}**.", ephemeral=True
            )
            return
        await interaction.followup.send(embed=build_weapon_attachment_embed(item))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WeaponAttachmentsCog(bot))
