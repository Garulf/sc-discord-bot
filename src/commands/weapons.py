"""The ``/weapon`` command: search the Star Citizen Wiki for an FPS / personal
weapon, show its key stats, and list the in-game shops where it can be bought.
Uses the shared API client stored on the bot (``bot.weapons_api``)."""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.starcitizenwiki_api import StarCitizenWikiError, Weapon
from src.starcitizenwiki_api.weapons import PurchaseLocation

# How many buy locations to list before collapsing the rest into a "+N more".
MAX_SHOPS_SHOWN = 8


def _format_number(value: Optional[float], suffix: str = "") -> Optional[str]:
    if value is None:
        return None
    rounded = round(value, 2)
    if rounded == int(rounded):
        rounded = int(rounded)
    return f"{rounded:,}{suffix}"


def _format_shop(shop: PurchaseLocation) -> str:
    """One line per shop: '12,345 aUEC — Terminal (Location, System)'."""
    price = _format_number(shop.price_buy, " aUEC") if shop.price_buy else "price n/a"
    place = " · ".join(part for part in (shop.location_name, shop.star_system) if part)
    terminal = shop.terminal_name or "Unknown terminal"
    suffix = f" ({place})" if place else ""
    return f"**{price}** — {terminal}{suffix}"


def build_weapon_embed(weapon: Weapon) -> discord.Embed:
    """Render a personal weapon from the wiki API as a Discord embed."""
    title = f"{weapon.manufacturer} {weapon.name}" if weapon.manufacturer else weapon.name
    embed = discord.Embed(
        title=title,
        url=weapon.web_url or None,
        color=0xE07B1B,
    )
    if weapon.description:
        description = weapon.description.strip()
        embed.description = description[:500] + ("…" if len(description) > 500 else "")
    if weapon.image_url:
        embed.set_thumbnail(url=weapon.image_url)

    classification = " · ".join(
        part for part in (weapon.classification, weapon.weapon_type) if part
    )
    if classification:
        embed.add_field(name="Type", value=classification, inline=False)

    if weapon.fire_mode:
        embed.add_field(name="Fire Mode", value=weapon.fire_mode, inline=True)

    if weapon.magazine_size is not None:
        embed.add_field(name="Magazine", value=str(weapon.magazine_size), inline=True)

    rpm = _format_number(weapon.rpm, " rpm")
    if rpm:
        embed.add_field(name="Rate of Fire", value=rpm, inline=True)

    alpha = _format_number(weapon.alpha_damage)
    if alpha:
        dps = _format_number(weapon.dps)
        value = f"{alpha} dmg" + (f" · {dps} DPS" if dps else "")
        embed.add_field(name="Damage", value=value, inline=True)

    rng = _format_number(weapon.effective_range, " m")
    if rng:
        embed.add_field(name="Effective Range", value=rng, inline=True)

    if weapon.ammunition_type:
        embed.add_field(name="Ammo", value=weapon.ammunition_type, inline=True)

    _add_shops_field(embed, weapon)

    embed.set_footer(text="Source: star-citizen.wiki · prices via UEX")
    return embed


def _add_shops_field(embed: discord.Embed, weapon: Weapon) -> None:
    """Add a 'Where to Buy' field, or a not-sold note when no shops are known."""
    shops = [s for s in weapon.purchase_locations if s.price_buy is not None]
    if not shops:
        embed.add_field(
            name="Where to Buy",
            value="No known in-game purchase locations.",
            inline=False,
        )
        return

    # Cheapest first so the best deal is at the top.
    shops.sort(key=lambda s: s.price_buy or float("inf"))
    lines = [_format_shop(s) for s in shops[:MAX_SHOPS_SHOWN]]
    remaining = len(shops) - MAX_SHOPS_SHOWN
    if remaining > 0:
        lines.append(f"…and {remaining} more location(s)")
    embed.add_field(name="Where to Buy", value="\n".join(lines), inline=False)


class WeaponsCog(commands.Cog):
    """FPS / personal weapon lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def weapon_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest weapon names as the user types, de-duplicated by display name."""
        if not current:
            return []
        try:
            results = await self.bot.weapons_api.search(current, limit=25)
        except StarCitizenWikiError:
            return []
        results.sort(key=lambda w: len(w.name))
        choices: list[app_commands.Choice[str]] = []
        seen: set[str] = set()
        for weapon in results:
            if weapon.name in seen:
                continue
            seen.add(weapon.name)
            choices.append(app_commands.Choice(name=weapon.name[:100], value=weapon.name[:100]))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(
        name="weapon", description="Look up Star Citizen FPS weapon info and where to buy it"
    )
    @app_commands.describe(name="Weapon name to search for (e.g. P4-AR, Arrowhead)")
    @app_commands.autocomplete(name=weapon_autocomplete)
    async def weapon(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            weapon = await self.bot.weapons_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(
                f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True
            )
            return
        if weapon is None:
            await interaction.followup.send(
                f"No weapon found matching **{name}**.", ephemeral=True
            )
            return
        await interaction.followup.send(embed=build_weapon_embed(weapon))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WeaponsCog(bot))
