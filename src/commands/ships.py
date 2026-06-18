"""The ``/ship`` command: search the Star Citizen Wiki for a vehicle and show
its key stats. Uses the shared API client stored on the bot (``bot.ships_api``)."""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.starcitizenwiki_api import StarCitizenWikiError, Vehicle
from src.uex_api import UEXError, VehiclePurchasePrice


def _format_number(value: Optional[float], suffix: str = "") -> Optional[str]:
    if value is None:
        return None
    rounded = round(value, 2)
    if rounded == int(rounded):
        rounded = int(rounded)
    return f"{rounded:,}{suffix}"


def _format_armor(vehicle: Vehicle) -> Optional[str]:
    parts = []
    if vehicle.deflection_physical:
        parts.append(f"Physical {vehicle.deflection_physical}")
    if vehicle.deflection_energy:
        parts.append(f"Energy {vehicle.deflection_energy}")
    return " · ".join(parts) if parts else None


def _format_signals(vehicle: Vehicle) -> Optional[str]:
    parts = []
    for label, value in (
        ("IR", vehicle.signal_ir),
        ("EM", vehicle.signal_em),
    ):
        formatted = _format_number(value)
        if formatted is not None:
            parts.append(f"{label} ×{formatted}")
    return " · ".join(parts) if parts else None


def build_ship_embed(
    vehicle: Vehicle, cheapest_auec: Optional[VehiclePurchasePrice] = None
) -> discord.Embed:
    """Render a vehicle from the wiki API as a Discord embed."""
    title = f"{vehicle.manufacturer} {vehicle.name}" if vehicle.manufacturer else vehicle.name
    embed = discord.Embed(
        title=title,
        url=vehicle.pledge_url or vehicle.web_url,
        color=0x1B98E0,
    )
    if vehicle.description:
        description = vehicle.description.strip()
        embed.description = description[:500] + ("…" if len(description) > 500 else "")
    if vehicle.image_url:
        embed.set_image(url=vehicle.image_url)

    classification = " · ".join(
        part for part in (vehicle.production_status, vehicle.size, vehicle.type) if part
    )
    if classification:
        embed.add_field(name="Status", value=classification.title(), inline=False)

    role = vehicle.role or (", ".join(vehicle.foci) if vehicle.foci else None)
    if role:
        embed.add_field(name="Role", value=role, inline=True)

    if vehicle.crew_min is not None or vehicle.crew_max is not None:
        if vehicle.crew_min == vehicle.crew_max:
            crew = str(vehicle.crew_max)
        else:
            crew = f"{vehicle.crew_min or 0}–{vehicle.crew_max or 0}"
        embed.add_field(name="Crew", value=crew, inline=True)

    cargo = _format_number(vehicle.cargo_capacity, " SCU")
    if cargo:
        embed.add_field(name="Cargo", value=cargo, inline=True)

    speed = _format_number(vehicle.scm_speed, " m/s")
    if speed:
        embed.add_field(name="SCM Speed", value=speed, inline=True)

    nav_speed = _format_number(vehicle.max_speed, " m/s")
    if nav_speed:
        embed.add_field(name="NAV Speed", value=nav_speed, inline=True)

    if vehicle.length or vehicle.width or vehicle.height:
        dims = " × ".join(
            _format_number(d) or "?" for d in (vehicle.length, vehicle.width, vehicle.height)
        )
        embed.add_field(name="Size (L×W×H)", value=f"{dims} m", inline=True)

    hull = _format_number(vehicle.health)
    if hull:
        shield = _format_number(vehicle.shield_hp)
        value = f"{hull} HP" + (f" · {shield} shield" if shield else "")
        embed.add_field(name="Hull", value=value, inline=True)

    armor = _format_armor(vehicle)
    if armor:
        embed.add_field(name="Armor (deflection)", value=armor, inline=True)

    signals = _format_signals(vehicle)
    if signals:
        embed.add_field(name="Signature (×)", value=signals, inline=True)

    if vehicle.msrp:
        embed.add_field(name="MSRP", value=f"${_format_number(vehicle.msrp)}", inline=True)

    footer = "Source: star-citizen.wiki"
    if cheapest_auec is not None and cheapest_auec.price_buy:
        auec = _format_number(cheapest_auec.price_buy, " aUEC")
        if cheapest_auec.terminal_name:
            value = f"{auec}\n{cheapest_auec.terminal_name}"
        else:
            value = auec or ""
        embed.add_field(name="In-Game Price", value=value, inline=True)
        footer = "Source: star-citizen.wiki · aUEC prices via UEX"

    embed.set_footer(text=footer)
    return embed


class ShipsCog(commands.Cog):
    """Ship/vehicle lookups against the Star Citizen Wiki API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def ship_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest ship names as the user types, de-duplicated by display name.

        Before anything is typed, show a default sample of ships rather than an
        empty list.
        """
        try:
            if current:
                results = await self.bot.ships_api.search(current, limit=25)
                results.sort(key=lambda v: len(v.name))
            else:
                results = await self.bot.ships_api.browse(limit=25)
        except StarCitizenWikiError:
            return []
        choices: list[app_commands.Choice[str]] = []
        seen: set[str] = set()
        for vehicle in results:
            if vehicle.name in seen:
                continue
            seen.add(vehicle.name)
            choices.append(app_commands.Choice(name=vehicle.name, value=vehicle.name))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="ship", description="Look up Star Citizen ship/vehicle info")
    @app_commands.describe(name="Ship name to search for (e.g. 300i, Cutlass Black)")
    @app_commands.autocomplete(name=ship_autocomplete)
    async def ship(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            vehicle = await self.bot.ships_api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(
                f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True
            )
            return
        if vehicle is None:
            await interaction.followup.send(
                f"No ship found matching **{name}**.", ephemeral=True
            )
            return
        cheapest = await self._cheapest_auec(vehicle.name)
        await interaction.followup.send(embed=build_ship_embed(vehicle, cheapest))

    async def _cheapest_auec(self, ship_name: str) -> Optional[VehiclePurchasePrice]:
        """Best-effort cheapest in-game (aUEC) buy price for a ship, or None.

        The wiki and UEX are independent sources, so this never blocks the
        ship lookup: any UEX error or unmatched name just omits the price.
        """
        try:
            match = await self.bot.vehicles_api.find(ship_name)
            if match is None or match.id is None:
                return None
            return await self.bot.vehicle_prices_api.cheapest_purchase(match.id)
        except UEXError:
            return None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShipsCog(bot))
