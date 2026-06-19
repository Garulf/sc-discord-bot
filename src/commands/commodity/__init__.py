"""The /commodity command group: find the best terminals to buy or sell a
commodity for aUEC in-game, and rank the most profitable commodity buy→sell
routes, with optional filters. Uses the shared UEX clients on the bot
(``bot.commodities_api``, ``bot.commodity_prices_api``, ``bot.terminals_api``
and ``bot.vehicles_api``)."""

from __future__ import annotations

from typing import Callable, Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.uex_api import Terminal, UEXError
from src.commands.formatting import format_number as _format_number_opt
from .constants import CONTAINER_CHOICES, PLACE_CHOICES, SYSTEM_CHOICES
from .embeds import build_commodity_embed
from .helpers import (
    buying_locations,
    commodity_filter_summary,
    matches_place,
    name_choices,
    selling_locations,
)
from .buy import handle as _handle_buy
from .sell import handle as _handle_sell
from .route import handle as _handle_route


class CommodityCog(commands.Cog):
    """Commodity buy/sell/route lookups against the UEX API."""

    commodity = app_commands.Group(name="commodity", description="Commodity trading commands")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def commodity_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            if current:
                results = await self.bot.commodities_api.search(current, limit=25)
            else:
                results = sorted(await self.bot.commodities_api.all(), key=lambda c: c.name)
        except UEXError:
            return []
        choices: list[app_commands.Choice[str]] = []
        seen: set[str] = set()
        for commodity in results:
            if commodity.name in seen:
                continue
            seen.add(commodity.name)
            choices.append(app_commands.Choice(name=commodity.name[:100], value=commodity.name[:100]))
            if len(choices) >= 25:
                break
        return choices

    async def ship_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            if current:
                results = await self.bot.vehicles_api.search(current, limit=25)
            else:
                results = sorted(await self.bot.vehicles_api.all(), key=lambda v: v.name)
        except UEXError:
            return []
        return name_choices(vehicle.name for vehicle in results)

    async def orbit_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._terminal_attr_choices(lambda t: t.orbit_name, current)

    async def terminal_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._terminal_attr_choices(lambda t: t.name, current)

    async def faction_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._terminal_attr_choices(lambda t: t.faction_name, current)

    async def _respond(
        self,
        interaction: discord.Interaction,
        name: str,
        *,
        selling: bool,
        system: Optional[app_commands.Choice[str]],
        place: Optional[app_commands.Choice[str]],
        exterior_cargo: Optional[bool],
    ) -> None:
        await interaction.response.defer()
        commodity = await self._find_commodity(interaction, name)
        if commodity is None:
            return
        prices = await self._collect_prices(
            interaction, commodity.id, system=system, place=place, exterior_cargo=exterior_cargo
        )
        if prices is None:
            return
        locations = selling_locations(prices) if selling else buying_locations(prices)
        filters = commodity_filter_summary(system, place, exterior_cargo)
        await interaction.followup.send(
            embed=build_commodity_embed(
                commodity, locations, selling=selling, filters=filters, show_system=system is None
            )
        )

    async def _find_commodity(self, interaction: discord.Interaction, name: str):
        try:
            commodity = await self.bot.commodities_api.find(name)
        except UEXError as e:
            await interaction.followup.send(
                f"Couldn't reach the UEX API right now: {e}", ephemeral=True
            )
            return None
        if commodity is None or commodity.id is None:
            await interaction.followup.send(
                f"No commodity found matching **{name}**.", ephemeral=True
            )
            return None
        return commodity

    async def _collect_prices(
        self,
        interaction: discord.Interaction,
        commodity_id: int,
        *,
        system: Optional[app_commands.Choice[str]],
        place: Optional[app_commands.Choice[str]],
        exterior_cargo: Optional[bool],
    ):
        try:
            prices = await self.bot.commodity_prices_api.for_commodity(commodity_id)
            if system is not None:
                target = system.value.lower()
                prices = [p for p in prices if (p.star_system_name or "").lower() == target]
            if place is not None:
                prices = [p for p in prices if matches_place(p, place.value)]
            if exterior_cargo is not None:
                docks = await self._exterior_terminal_ids()
                prices = [p for p in prices if (p.id_terminal in docks) == exterior_cargo]
            return prices
        except UEXError as e:
            await interaction.followup.send(
                f"Couldn't reach the UEX API right now: {e}", ephemeral=True
            )
            return None

    async def _exterior_terminal_ids(self) -> set[int]:
        terminals = await self.bot.terminals_api.all(terminal_type="commodity")
        return {t.id for t in terminals if t.has_loading_dock and t.id is not None}

    async def _terminal_attr_choices(
        self, getter: Callable[[Terminal], Optional[str]], current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            terminals = await self.bot.terminals_api.all(terminal_type="commodity")
        except UEXError:
            return []
        values = {getter(t) for t in terminals if getter(t)}
        needle = current.strip().lower()
        matches = [v for v in sorted(values) if not needle or needle in v.lower()]
        return name_choices(matches)

    @commodity.command(name="buy", description="Find the cheapest terminals to buy a commodity for aUEC")
    @app_commands.describe(
        name="Commodity name to search for (e.g. Gold, Laranite)",
        system="Limit to a star system",
        place="Limit to a kind of location",
        exterior_cargo="Only terminals with an exterior loading dock",
    )
    @app_commands.choices(system=SYSTEM_CHOICES, place=PLACE_CHOICES)
    @app_commands.autocomplete(name=commodity_autocomplete)
    async def buy(
        self,
        interaction: discord.Interaction,
        name: str,
        system: Optional[app_commands.Choice[str]] = None,
        place: Optional[app_commands.Choice[str]] = None,
        exterior_cargo: Optional[bool] = None,
    ):
        await _handle_buy(self, interaction, name, system, place, exterior_cargo)

    @commodity.command(name="sell", description="Find the best-paying terminals to sell a commodity for aUEC")
    @app_commands.describe(
        name="Commodity name to search for (e.g. Gold, Laranite)",
        system="Limit to a star system",
        place="Limit to a kind of location",
        exterior_cargo="Only terminals with an exterior loading dock",
    )
    @app_commands.choices(system=SYSTEM_CHOICES, place=PLACE_CHOICES)
    @app_commands.autocomplete(name=commodity_autocomplete)
    async def sell(
        self,
        interaction: discord.Interaction,
        name: str,
        system: Optional[app_commands.Choice[str]] = None,
        place: Optional[app_commands.Choice[str]] = None,
        exterior_cargo: Optional[bool] = None,
    ):
        await _handle_sell(self, interaction, name, system, place, exterior_cargo)

    @commodity.command(name="route", description="Show the top 3 most profitable commodity trade routes")
    @app_commands.describe(
        ship="Select a ship to use for route",
        investment="Budget in aUEC to spend buying cargo",
        scu="Cargo capacity in SCU to haul",
        commodity="Only routes for this commodity",
        star_system_start="Buy in this star system",
        star_system_end="Sell in this star system",
        orbit_start="Buy at this orbit/location",
        orbit_end="Sell at this orbit/location",
        terminal_start="Buy at this terminal",
        container_size="Only terminals accepting this container size",
        faction="Only terminals controlled by this faction",
        is_loop="Prefer round-trip loop routes (UEX link only)",
        has_loading_dock="Only terminals with an exterior loading dock",
        is_auto_load="Only terminals with auto-load",
        safe_commodities="Exclude illegal commodities",
        is_nqa="Only no-questions-asked terminals",
        is_monitored="Only monitored terminals (UEX link only)",
        is_space_station="Only space-station terminals",
        has_refuel="Only terminals with refuel",
        is_predictable="Only predictable routes (UEX link only)",
        is_player_owned="Only player-owned terminals",
    )
    @app_commands.choices(
        star_system_start=SYSTEM_CHOICES,
        star_system_end=SYSTEM_CHOICES,
        container_size=CONTAINER_CHOICES,
    )
    @app_commands.autocomplete(
        ship=ship_autocomplete,
        commodity=commodity_autocomplete,
        orbit_start=orbit_autocomplete,
        orbit_end=orbit_autocomplete,
        terminal_start=terminal_autocomplete,
        faction=faction_autocomplete,
    )
    async def route(
        self,
        interaction: discord.Interaction,
        ship: Optional[str] = None,
        investment: Optional[int] = None,
        scu: Optional[int] = None,
        commodity: Optional[str] = None,
        star_system_start: Optional[app_commands.Choice[str]] = None,
        star_system_end: Optional[app_commands.Choice[str]] = None,
        orbit_start: Optional[str] = None,
        orbit_end: Optional[str] = None,
        terminal_start: Optional[str] = None,
        container_size: Optional[app_commands.Choice[int]] = None,
        faction: Optional[str] = None,
        is_loop: Optional[bool] = None,
        has_loading_dock: Optional[bool] = None,
        is_auto_load: Optional[bool] = None,
        safe_commodities: Optional[bool] = None,
        is_nqa: Optional[bool] = None,
        is_monitored: Optional[bool] = None,
        is_space_station: Optional[bool] = None,
        has_refuel: Optional[bool] = None,
        is_predictable: Optional[bool] = None,
        is_player_owned: Optional[bool] = None,
    ):
        await _handle_route(
            self, interaction,
            ship=ship, investment=investment, scu=scu, commodity=commodity,
            star_system_start=star_system_start, star_system_end=star_system_end,
            orbit_start=orbit_start, orbit_end=orbit_end, terminal_start=terminal_start,
            container_size=container_size, faction=faction, is_loop=is_loop,
            has_loading_dock=has_loading_dock, is_auto_load=is_auto_load,
            safe_commodities=safe_commodities, is_nqa=is_nqa, is_monitored=is_monitored,
            is_space_station=is_space_station, has_refuel=has_refuel,
            is_predictable=is_predictable, is_player_owned=is_player_owned,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommodityCog(bot))
