"""The ``/shipprice`` command: look up where a ship can be bought or rented for
aUEC in-game, using the shared UEX API clients on the bot (``bot.vehicles_api``
and ``bot.vehicle_prices_api``)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.autocomplete import item_choices
from src.commands.formatting import format_number as _format_number
from src.starcitizenwiki_api import StarCitizenWikiError
from src.uex_api import UEXError, Vehicle, VehiclePurchasePrice, VehicleRentalPrice

MAX_LOCATIONS_SHOWN = 8


def _ship_title(vehicle: Vehicle) -> str:
    if vehicle.company_name:
        return f"{vehicle.company_name} {vehicle.name}"
    return vehicle.name_full or vehicle.name


def build_shipprice_embed(
    vehicle: Vehicle,
    purchases: list[VehiclePurchasePrice],
    rentals: list[VehicleRentalPrice],
    image_url: str | None = None,
) -> discord.Embed:
    """Render a ship's in-game buy/rent locations as a Discord embed."""
    embed = discord.Embed(title=_ship_title(vehicle), color=0x1B98E0)
    if image_url:
        embed.set_image(url=image_url)

    _add_purchase_field(embed, purchases)
    _add_rental_field(embed, rentals)

    embed.set_footer(text="In-game aUEC prices via UEX")
    return embed


def _add_purchase_field(embed: discord.Embed, purchases: list[VehiclePurchasePrice]) -> None:
    """Add a 'Where to Buy' field, cheapest first, or a not-sold note."""
    priced = [p for p in purchases if p.price_buy]
    if not priced:
        embed.add_field(
            name="Where to Buy",
            value="No known in-game purchase locations.",
            inline=False,
        )
        return

    priced.sort(key=lambda p: p.price_buy or float("inf"))
    lines = [
        f"**{_format_number(p.price_buy, ' aUEC')}** — {p.terminal_name or 'Unknown terminal'}"
        for p in priced[:MAX_LOCATIONS_SHOWN]
    ]
    remaining = len(priced) - MAX_LOCATIONS_SHOWN
    if remaining > 0:
        lines.append(f"…and {remaining} more location(s)")
    embed.add_field(name="Where to Buy", value="\n".join(lines), inline=False)


def _add_rental_field(embed: discord.Embed, rentals: list[VehicleRentalPrice]) -> None:
    """Add a 'Where to Rent' field with the cheapest rental, when available."""
    priced = [r for r in rentals if r.price_rent]
    if not priced:
        return
    priced.sort(key=lambda r: r.price_rent or float("inf"))
    cheapest = priced[0]
    value = f"**{_format_number(cheapest.price_rent, ' aUEC')}** — {cheapest.terminal_name or 'Unknown terminal'}"
    embed.add_field(name="Cheapest Rental", value=value, inline=False)


class ShipPriceCog(commands.Cog):
    """In-game ship buy/rent price lookups against the UEX API."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def ship_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Suggest ship names as the user types, de-duplicated by display name.

        Before anything is typed, show a default sample of ships rather than an
        empty list.
        """
        try:
            if current:
                results = await self.bot.vehicles_api.search(current, limit=25)
            else:
                results = sorted(await self.bot.vehicles_api.all(), key=lambda v: v.name)
        except UEXError:
            return []
        return item_choices(results)

    @app_commands.command(name="shipprice", description="Find where to buy or rent a ship for aUEC in-game")
    @app_commands.describe(name="Ship name to search for (e.g. Cutlass Black, 300i)")
    @app_commands.autocomplete(name=ship_autocomplete)
    async def shipprice(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        try:
            vehicle = await self.bot.vehicles_api.find(name)
        except UEXError as e:
            await interaction.followup.send(f"Couldn't reach the UEX API right now: {e}", ephemeral=True)
            return
        if vehicle is None or vehicle.id is None:
            await interaction.followup.send(f"No ship found matching **{name}**.", ephemeral=True)
            return

        try:
            purchases = await self.bot.vehicle_prices_api.purchases_for_vehicle(vehicle.id)
            rentals = await self.bot.vehicle_prices_api.rentals_for_vehicle(vehicle.id)
        except UEXError as e:
            await interaction.followup.send(f"Couldn't reach the UEX API right now: {e}", ephemeral=True)
            return

        image_url = await self._image_url(vehicle.name)
        await interaction.followup.send(embed=build_shipprice_embed(vehicle, purchases, rentals, image_url))

    async def _image_url(self, ship_name: str) -> str | None:
        """Best-effort ship thumbnail from the wiki, or None.

        UEX has no images, so this is sourced separately and never blocks the
        price lookup: any wiki error or unmatched name just omits the image.
        """
        try:
            match = await self.bot.ships_api.find(ship_name)
        except StarCitizenWikiError:
            return None
        return match.image_url if match is not None else None


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ShipPriceCog(bot))
