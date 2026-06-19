"""The /commodity command group: find the best terminals to buy or sell a
commodity for aUEC in-game, and rank the most profitable commodity buy→sell
routes, with optional filters. Uses the shared UEX clients on the bot
(``bot.commodities_api``, ``bot.commodity_prices_api``, ``bot.terminals_api``
and ``bot.vehicles_api``).

Subcommand logic lives in individual files; this module contains only the Cog
class (autocomplete stubs and command registration)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .buy import handle as _handle_buy
from .route import handle as _handle_route
from .sell import handle as _handle_sell
from .shared import (
    CONTAINER_CHOICES,
    PLACE_CHOICES,
    SYSTEM_CHOICES,
    autocomplete_commodity,
    autocomplete_faction,
    autocomplete_orbit,
    autocomplete_ship,
    autocomplete_terminal,
)


class CommodityCog(commands.Cog):
    """Commodity buy/sell/route lookups against the UEX API."""

    commodity = app_commands.Group(name="commodity", description="Commodity trading commands")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def commodity_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_commodity(self, current)

    async def ship_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await autocomplete_ship(self, current)

    async def orbit_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_orbit(self, current)

    async def terminal_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_terminal(self, current)

    async def faction_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await autocomplete_faction(self, current)

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
        system: app_commands.Choice[str] | None = None,
        place: app_commands.Choice[str] | None = None,
        exterior_cargo: bool | None = None,
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
        system: app_commands.Choice[str] | None = None,
        place: app_commands.Choice[str] | None = None,
        exterior_cargo: bool | None = None,
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
        ship: str | None = None,
        investment: int | None = None,
        scu: int | None = None,
        commodity: str | None = None,
        star_system_start: app_commands.Choice[str] | None = None,
        star_system_end: app_commands.Choice[str] | None = None,
        orbit_start: str | None = None,
        orbit_end: str | None = None,
        terminal_start: str | None = None,
        container_size: app_commands.Choice[int] | None = None,
        faction: str | None = None,
        is_loop: bool | None = None,
        has_loading_dock: bool | None = None,
        is_auto_load: bool | None = None,
        safe_commodities: bool | None = None,
        is_nqa: bool | None = None,
        is_monitored: bool | None = None,
        is_space_station: bool | None = None,
        has_refuel: bool | None = None,
        is_predictable: bool | None = None,
        is_player_owned: bool | None = None,
    ):
        await _handle_route(
            self,
            interaction,
            ship=ship,
            investment=investment,
            scu=scu,
            commodity=commodity,
            star_system_start=star_system_start,
            star_system_end=star_system_end,
            orbit_start=orbit_start,
            orbit_end=orbit_end,
            terminal_start=terminal_start,
            container_size=container_size,
            faction=faction,
            is_loop=is_loop,
            has_loading_dock=has_loading_dock,
            is_auto_load=is_auto_load,
            safe_commodities=safe_commodities,
            is_nqa=is_nqa,
            is_monitored=is_monitored,
            is_space_station=is_space_station,
            has_refuel=has_refuel,
            is_predictable=is_predictable,
            is_player_owned=is_player_owned,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommodityCog(bot))
