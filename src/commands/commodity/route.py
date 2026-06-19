"""Handler for /commodity route — ranks the most profitable trade routes."""

from __future__ import annotations

from dataclasses import dataclass

import discord
from discord import app_commands

from src.uex_api import UEXError
from src.uex_api.models import Commodity, CommodityPrice, Terminal, Vehicle

from .shared import (
    MAX_ROUTES,
    Route,
    TerminalPredicate,
    build_routes_embed,
    build_uex_url,
    capacity,
    lookup_id,
    route_filter_summary,
    slugify,
    terminal_predicate,
    terminal_slug,
    tradeable_scu,
)


@dataclass(frozen=True)
class RouteFilters:
    """Every option the user can pass to /commodity route, in one bundle.

    The slash command must declare each option explicitly (Discord requirement),
    so it builds this and hands it to :func:`handle` instead of threading two
    dozen arguments through every step.
    """

    ship: str | None = None
    investment: int | None = None
    scu: int | None = None
    commodity: str | None = None
    star_system_start: app_commands.Choice[str] | None = None
    star_system_end: app_commands.Choice[str] | None = None
    orbit_start: str | None = None
    orbit_end: str | None = None
    terminal_start: str | None = None
    container_size: app_commands.Choice[int] | None = None
    faction: str | None = None
    is_loop: bool | None = None
    has_loading_dock: bool | None = None
    is_auto_load: bool | None = None
    safe_commodities: bool | None = None
    is_nqa: bool | None = None
    is_monitored: bool | None = None
    is_space_station: bool | None = None
    has_refuel: bool | None = None
    is_predictable: bool | None = None
    is_player_owned: bool | None = None

    @property
    def system_start(self) -> str | None:
        return self.star_system_start.value if self.star_system_start else None

    @property
    def system_end(self) -> str | None:
        return self.star_system_end.value if self.star_system_end else None

    @property
    def container(self) -> int | None:
        return self.container_size.value if self.container_size else None

    @property
    def terminal_flags(self) -> dict[str, bool | None]:
        """The boolean toggles that constrain which terminals qualify."""
        return {
            "has_loading_dock": self.has_loading_dock,
            "is_auto_load": self.is_auto_load,
            "is_nqa": self.is_nqa,
            "has_refuel": self.has_refuel,
            "is_player_owned": self.is_player_owned,
            "is_space_station": self.is_space_station,
        }

    @property
    def toggles(self) -> list[str]:
        """Human-readable labels for the filters the user turned on."""
        labelled = (
            ("Loop", self.is_loop),
            ("Loading dock", self.has_loading_dock),
            ("Auto-load", self.is_auto_load),
            ("Legal only", self.safe_commodities),
            ("NQA", self.is_nqa),
            ("Monitored", self.is_monitored),
            ("Space station", self.is_space_station),
            ("Refuel", self.has_refuel),
            ("Predictable", self.is_predictable),
            ("Player-owned", self.is_player_owned),
        )
        return [label for label, value in labelled if value]


class _RouteAborted(Exception):
    """Raised once a user-facing error has been sent, to stop further handling."""


async def handle(
    cog,
    interaction: discord.Interaction,
    *,
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
) -> None:
    filters = RouteFilters(
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
    await interaction.response.defer()
    try:
        prices, terminals = await _fetch_market_data(cog, interaction)
        resolved_commodity = await _resolve_commodity(cog, interaction, filters.commodity)
        vehicle = await _resolve_vehicle(cog, filters.ship)
        allowed_commodities = await _resolve_allowed_commodities(cog, enabled=filters.safe_commodities)
    except _RouteAborted:
        return

    origin, destination = _build_predicates(filters)
    routes = best_routes(
        prices,
        {t.id: t for t in terminals if t.id is not None},
        origin=origin,
        destination=destination,
        id_commodity=resolved_commodity.id if resolved_commodity else None,
        capacity=capacity(vehicle, filters.scu),
        investment=filters.investment,
        allowed_commodities=allowed_commodities,
    )
    if not routes:
        await interaction.followup.send("No profitable routes match those filters.", ephemeral=True)
        return

    summary = route_filter_summary(
        ship=filters.ship,
        investment=filters.investment,
        scu=filters.scu,
        commodity=filters.commodity,
        system_start=filters.system_start,
        system_end=filters.system_end,
        orbit_start=filters.orbit_start,
        orbit_end=filters.orbit_end,
        terminal_start=filters.terminal_start,
        container=filters.container,
        faction=filters.faction,
        toggles=filters.toggles,
    )
    url = _build_uex_url(filters, vehicle, terminals, resolved_commodity.name if resolved_commodity else None)
    await interaction.followup.send(embed=build_routes_embed(routes, filters=summary, url=url))


# ---------------------------------------------------------------------------
# Route-finding algorithm (was routes.py)
# ---------------------------------------------------------------------------


def best_routes(
    prices: list[CommodityPrice],
    terminals_by_id: dict[int, Terminal],
    *,
    origin: TerminalPredicate,
    destination: TerminalPredicate,
    id_commodity: int | None,
    capacity: int | None,
    investment: int | None,
    allowed_commodities: set[int] | None = None,
) -> list[Route]:
    """Best buy→sell route per commodity, ranked by trip profit, capped at MAX_ROUTES."""
    buys: dict[int, list[tuple[CommodityPrice, Terminal]]] = {}
    sells: dict[int, list[tuple[CommodityPrice, Terminal]]] = {}

    for row in prices:
        commodity_id = row.id_commodity
        if commodity_id is None:
            continue
        if id_commodity is not None and commodity_id != id_commodity:
            continue
        if allowed_commodities is not None and commodity_id not in allowed_commodities:
            continue
        terminal = terminals_by_id.get(row.id_terminal)
        if terminal is None:
            continue
        if row.price_buy and (row.scu_buy or 0) > 0 and origin(terminal):
            buys.setdefault(commodity_id, []).append((row, terminal))
        if row.price_sell and destination(terminal):
            sells.setdefault(commodity_id, []).append((row, terminal))

    routes: list[Route] = []
    for commodity_id, buy_options in buys.items():
        sell_options = sells.get(commodity_id)
        if not sell_options:
            continue
        pairs = _commodity_routes(buy_options, sell_options, capacity, investment)
        if not pairs:
            continue
        pairs.sort(key=lambda r: r.total_profit or 0.0, reverse=True)
        if id_commodity is None:
            routes.append(pairs[0])
        else:
            routes.extend(pairs)

    routes.sort(key=lambda r: r.total_profit or 0.0, reverse=True)
    return routes[:MAX_ROUTES]


def _commodity_routes(
    buy_options: list[tuple[CommodityPrice, Terminal]],
    sell_options: list[tuple[CommodityPrice, Terminal]],
    cap: int | None,
    investment: int | None,
) -> list[Route]:
    """Every viable buy→sell terminal pairing for one commodity, stock-limited."""
    routes: list[Route] = []
    for buy_row, buy_terminal in buy_options:
        for sell_row, sell_terminal in sell_options:
            if buy_terminal.id == sell_terminal.id:
                continue
            profit = (sell_row.price_sell or 0.0) - (buy_row.price_buy or 0.0)
            if profit <= 0:
                continue
            scu = tradeable_scu(
                buy_row.price_buy or 0.0,
                buy_row.scu_buy or 0.0,
                sell_row.scu_sell or 0.0,
                cap,
                investment,
            )
            if scu <= 0:
                continue
            routes.append(
                Route(
                    commodity_name=buy_row.commodity_name or "Unknown",
                    buy_terminal=buy_terminal,
                    sell_terminal=sell_terminal,
                    buy_price=buy_row.price_buy or 0.0,
                    sell_price=sell_row.price_sell or 0.0,
                    profit_per_scu=profit,
                    scu=scu,
                    total_profit=profit * scu,
                )
            )
    return routes


# ---------------------------------------------------------------------------
# Helpers local to /commodity route
# ---------------------------------------------------------------------------


async def _fetch_market_data(cog, interaction: discord.Interaction) -> tuple[list[CommodityPrice], list[Terminal]]:
    try:
        prices = await cog.bot.commodity_prices_api.all()
        terminals = await cog.bot.terminals_api.all(terminal_type="commodity")
    except UEXError as e:
        await interaction.followup.send(f"Couldn't reach the UEX API right now: {e}", ephemeral=True)
        raise _RouteAborted from e
    return prices, terminals


async def _resolve_commodity(cog, interaction: discord.Interaction, query: str | None) -> Commodity | None:
    if not query:
        return None
    try:
        match = await cog.bot.commodities_api.find(query)
    except UEXError:
        match = None
    if match is None or match.id is None:
        await interaction.followup.send(f"No commodity found matching **{query}**.", ephemeral=True)
        raise _RouteAborted
    return match


async def _resolve_vehicle(cog, ship: str | None) -> Vehicle | None:
    if not ship:
        return None
    try:
        return await cog.bot.vehicles_api.find(ship)
    except UEXError:
        return None


async def _resolve_allowed_commodities(cog, *, enabled: bool | None) -> set[int] | None:
    if not enabled:
        return None
    try:
        catalogue = await cog.bot.commodities_api.all()
    except UEXError:
        catalogue = []
    return {c.id for c in catalogue if c.id is not None and not c.is_illegal}


def _build_predicates(filters: RouteFilters):
    origin = terminal_predicate(
        system=filters.system_start,
        orbit=filters.orbit_start,
        terminal_name=filters.terminal_start,
        faction=filters.faction,
        container_size=filters.container,
        **filters.terminal_flags,
    )
    destination = terminal_predicate(
        system=filters.system_end,
        orbit=filters.orbit_end,
        terminal_name=None,
        faction=filters.faction,
        container_size=filters.container,
        **filters.terminal_flags,
    )
    return origin, destination


def _build_uex_url(
    filters: RouteFilters, vehicle: Vehicle | None, terminals: list[Terminal], commodity_name: str | None
) -> str:
    return build_uex_url(
        {
            "id_vehicle": vehicle.id if vehicle else None,
            "investment": f"{filters.investment:,}" if filters.investment else None,
            "orbit_origin": slugify(filters.orbit_start) if filters.orbit_start else None,
            "orbit_destination": slugify(filters.orbit_end) if filters.orbit_end else None,
            "terminal_origin": terminal_slug(terminals, filters.terminal_start),
            "id_star_system_origin": lookup_id(
                terminals, lambda t: t.star_system_name, filters.system_start, lambda t: t.id_star_system
            ),
            "id_star_system_destination": lookup_id(
                terminals, lambda t: t.star_system_name, filters.system_end, lambda t: t.id_star_system
            ),
            "scu": filters.scu,
            "commodity": slugify(commodity_name) if commodity_name else None,
            "mcs": filters.container,
            "id_faction": lookup_id(terminals, lambda t: t.faction_name, filters.faction, lambda t: t.id_faction),
            "is_loop": 1 if filters.is_loop else None,
            "has_loading_dock": 1 if filters.has_loading_dock else None,
            "is_auto_load": 1 if filters.is_auto_load else None,
            "safe_commodities": 1 if filters.safe_commodities else None,
            "is_nqa": 1 if filters.is_nqa else None,
            "is_monitored": 1 if filters.is_monitored else None,
            "is_space_station": 1 if filters.is_space_station else None,
            "has_refuel": 1 if filters.has_refuel else None,
            "is_predictable": 1 if filters.is_predictable else None,
            "is_player_owned": 1 if filters.is_player_owned else None,
        }
    )
