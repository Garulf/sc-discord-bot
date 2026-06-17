"""The ``/commodity`` and ``/commodity route`` commands: find the best terminals
to buy or sell a commodity for aUEC in-game, and rank the most profitable
commodity buy→sell routes, with optional filters. Uses the shared UEX clients
on the bot (``bot.commodities_api``, ``bot.commodity_prices_api``,
``bot.terminals_api`` and ``bot.vehicles_api``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlencode

import discord
from discord import app_commands
from discord.ext import commands

from src.uex_api import Commodity, CommodityPrice, Terminal, UEXError, Vehicle

# How many terminals to list before collapsing the rest into a "+N more".
MAX_LOCATIONS_SHOWN = 8

BUY_COLOR = 0x2ECC71
SELL_COLOR = 0xF1C40F
LOSS_COLOR = 0xE74C3C

MAX_ROUTES = 3
ROUTE_COLOR = 0x2ECC71
UEX_ROUTES_URL = "https://uexcorp.space/trade/routes"

SYSTEM_CHOICES = [
    app_commands.Choice(name="Stanton", value="Stanton"),
    app_commands.Choice(name="Pyro", value="Pyro"),
    app_commands.Choice(name="Nyx", value="Nyx"),
]
PLACE_CHOICES = [
    app_commands.Choice(name="Station", value="station"),
    app_commands.Choice(name="Planet", value="planet"),
    app_commands.Choice(name="Outpost", value="outpost"),
]
CONTAINER_CHOICES = [
    app_commands.Choice(name=f"{size} SCU", value=size)
    for size in (1, 2, 4, 8, 16, 24, 32)
]

TerminalPredicate = Callable[[Terminal], bool]


def _format_number(value: Optional[float], suffix: str = "") -> str:
    if value is None:
        return "?"
    rounded = round(value, 2)
    if rounded == int(rounded):
        rounded = int(rounded)
    return f"{rounded:,}{suffix}"


def _matches_place(price: CommodityPrice, place: str) -> bool:
    """Whether a price row's terminal matches a requested place type.

    'planet' covers planetside landing zones (cities) as well as bare planet
    surfaces; 'station' and 'outpost' map straight through.
    """
    if place == "planet":
        return price.place_type in ("planet", "city")
    return price.place_type == place


def _buying_locations(prices: list[CommodityPrice]) -> list[CommodityPrice]:
    """Terminals selling the commodity, cheapest first."""
    priced = [p for p in prices if p.price_buy]
    priced.sort(key=lambda p: p.price_buy or float("inf"))
    return priced


def _selling_locations(prices: list[CommodityPrice]) -> list[CommodityPrice]:
    """Terminals buying the commodity, highest payout first."""
    priced = [p for p in prices if p.price_sell]
    priced.sort(key=lambda p: p.price_sell or 0.0, reverse=True)
    return priced


def _commodity_filter_summary(
    system: Optional[app_commands.Choice[str]],
    place: Optional[app_commands.Choice[str]],
    exterior_cargo: Optional[bool],
) -> Optional[str]:
    parts = []
    if system is not None:
        parts.append(system.name)
    if place is not None:
        parts.append(place.name)
    if exterior_cargo is not None:
        parts.append("Exterior cargo" if exterior_cargo else "No exterior cargo")
    return " · ".join(parts) if parts else None


def _location_line(price: CommodityPrice, value: Optional[float], *, show_system: bool) -> str:
    auec = _format_number(value, " aUEC")
    suffix = f" ({price.star_system_name})" if show_system and price.star_system_name else ""
    return f"**{auec}** — {price.terminal_name or 'Unknown terminal'}{suffix}"


def build_commodity_embed(
    commodity: Commodity,
    locations: list[CommodityPrice],
    *,
    selling: bool,
    filters: Optional[str] = None,
    show_system: bool = True,
) -> discord.Embed:
    """Render a commodity's best buy/sell terminals as a Discord embed."""
    action = "Sell" if selling else "Buy"
    embed = discord.Embed(
        title=f"{commodity.name} — Where to {action}",
        color=SELL_COLOR if selling else BUY_COLOR,
    )
    if filters:
        embed.description = f"Filters: {filters}"

    if not locations:
        embed.add_field(
            name=f"Best places to {action.lower()}",
            value="No matching terminals found.",
            inline=False,
        )
        embed.set_footer(text="In-game aUEC prices via UEX")
        return embed

    lines = []
    for price in locations[:MAX_LOCATIONS_SHOWN]:
        value = price.price_sell if selling else price.price_buy
        lines.append(_location_line(price, value, show_system=show_system))
    remaining = len(locations) - MAX_LOCATIONS_SHOWN
    if remaining > 0:
        lines.append(f"…and {remaining} more terminal(s)")

    embed.add_field(name=f"Best places to {action.lower()}", value="\n".join(lines), inline=False)
    embed.set_footer(text="In-game aUEC prices via UEX · per unit")
    return embed


def build_trade_embed(
    commodity: Commodity,
    buy: CommodityPrice,
    sell: CommodityPrice,
    *,
    filters: Optional[str] = None,
    show_system: bool = True,
) -> discord.Embed:
    """Render the best buy→sell route for a commodity as a Discord embed."""
    profit = (sell.price_sell or 0.0) - (buy.price_buy or 0.0)
    embed = discord.Embed(
        title=f"{commodity.name} — Best Trade Route",
        color=BUY_COLOR if profit > 0 else LOSS_COLOR,
    )
    if filters:
        embed.description = f"Filters: {filters}"

    embed.add_field(name="Buy", value=_route_leg(buy, buy.price_buy, show_system=show_system), inline=True)
    embed.add_field(name="Sell", value=_route_leg(sell, sell.price_sell, show_system=show_system), inline=True)

    summary = f"**{_format_number(profit, ' aUEC')}** / unit"
    if buy.price_buy:
        roi = profit / buy.price_buy * 100
        summary += f"\n{_format_number(roi)}% ROI"
    embed.add_field(name="Profit", value=summary, inline=True)

    embed.set_footer(text="In-game aUEC prices via UEX · per unit")
    return embed


def _route_leg(price: CommodityPrice, value: Optional[float], *, show_system: bool) -> str:
    auec = _format_number(value, " aUEC")
    location = price.terminal_name or "Unknown terminal"
    if show_system and price.star_system_name:
        location += f" ({price.star_system_name})"
    return f"**{auec}**\n{location}"


@dataclass(frozen=True)
class Route:
    commodity_name: str
    buy_terminal: Terminal
    sell_terminal: Terminal
    buy_price: float
    sell_price: float
    profit_per_scu: float
    scu: Optional[int]
    total_profit: Optional[float]


def _terminal_predicate(
    *,
    system: Optional[str],
    orbit: Optional[str],
    terminal_name: Optional[str],
    faction: Optional[str],
    container_size: Optional[int],
    has_loading_dock: Optional[bool] = None,
    is_auto_load: Optional[bool] = None,
    is_nqa: Optional[bool] = None,
    has_refuel: Optional[bool] = None,
    is_player_owned: Optional[bool] = None,
    is_space_station: Optional[bool] = None,
) -> TerminalPredicate:
    def matches(terminal: Terminal) -> bool:
        if system and (terminal.star_system_name or "").lower() != system.lower():
            return False
        if orbit and (terminal.orbit_name or "").lower() != orbit.lower():
            return False
        if terminal_name and terminal_name.lower() not in (terminal.name or "").lower():
            return False
        if faction and (terminal.faction_name or "").lower() != faction.lower():
            return False
        if container_size and (terminal.max_container_size or 0) < container_size:
            return False
        if has_loading_dock and not terminal.has_loading_dock:
            return False
        if is_auto_load and not terminal.is_auto_load:
            return False
        if is_nqa and not terminal.is_nqa:
            return False
        if has_refuel and not terminal.is_refuel:
            return False
        if is_player_owned and not terminal.is_player_owned:
            return False
        if is_space_station and not terminal.is_space_station:
            return False
        return True

    return matches


def _tradeable_scu(
    buy_price: float,
    scu_buy: float,
    scu_sell: float,
    capacity: Optional[int],
    investment: Optional[int],
) -> int:
    """SCU actually movable on a trip: limited by supply at the origin, the
    ship's hold and the budget. Destination demand only caps the haul when it
    is actually reported (UEX treats unknown demand as "sell what you carry").
    """
    caps: list[float] = [scu_buy]
    if scu_sell > 0:
        caps.append(scu_sell)
    if capacity is not None:
        caps.append(capacity)
    if investment is not None and buy_price:
        caps.append(investment / buy_price)
    return int(min(caps))


def _capacity(vehicle: Optional[Vehicle], scu: Optional[int]) -> Optional[int]:
    caps = []
    if vehicle is not None and vehicle.scu:
        caps.append(int(vehicle.scu))
    if scu:
        caps.append(scu)
    return min(caps) if caps else None


def _lookup_id(
    terminals: list[Terminal],
    getter: Callable[[Terminal], Optional[str]],
    value: Optional[str],
    id_getter: Callable[[Terminal], Optional[int]],
) -> Optional[int]:
    if not value:
        return None
    target = value.lower()
    for terminal in terminals:
        name = getter(terminal)
        if name and name.lower() == target:
            return id_getter(terminal)
    return None


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _terminal_slug(terminals: list[Terminal], value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    target = value.lower()
    for terminal in terminals:
        if target in (terminal.name or "").lower():
            return _slugify(terminal.name or "")
    return None


def build_uex_url(params: dict[str, object]) -> str:
    """A UEX route-finder deep link carrying the provided filters as query
    params (matching the site's ``?id_vehicle=...&orbit_origin=...`` form).

    Entities UEX keys by id (vehicle, star system, faction) use the id;
    orbit/terminal/commodity use the name slug the site expects.
    """
    query = {key: value for key, value in params.items() if value is not None}
    if not query:
        return UEX_ROUTES_URL
    return f"{UEX_ROUTES_URL}?{urlencode(query)}"


def best_routes(
    prices: list[CommodityPrice],
    terminals_by_id: dict[int, Terminal],
    *,
    origin: TerminalPredicate,
    destination: TerminalPredicate,
    id_commodity: Optional[int],
    capacity: Optional[int],
    investment: Optional[int],
    allowed_commodities: Optional[set[int]] = None,
) -> list[Route]:
    """Best buy→sell route per commodity, ranked by trip profit, capped at
    ``MAX_ROUTES``.

    Only terminals with real supply (``scu_buy``) and demand (``scu_sell``) are
    considered, and each candidate pair's haul is limited by that stock (plus
    the ship's hold and budget when given), so the ranking reflects achievable
    trip income rather than headline price spread.
    """
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
        # For a single commodity, show its best terminal pairings; otherwise keep
        # one route per commodity so the default top list stays varied.
        if id_commodity is None:
            routes.append(pairs[0])
        else:
            routes.extend(pairs)

    routes.sort(key=lambda r: r.total_profit or 0.0, reverse=True)
    return routes[:MAX_ROUTES]


def _commodity_routes(
    buy_options: list[tuple[CommodityPrice, Terminal]],
    sell_options: list[tuple[CommodityPrice, Terminal]],
    capacity: Optional[int],
    investment: Optional[int],
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
            scu = _tradeable_scu(
                buy_row.price_buy or 0.0,
                buy_row.scu_buy or 0.0,
                sell_row.scu_sell or 0.0,
                capacity,
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


def build_routes_embed(
    routes: list[Route], *, filters: Optional[str], url: str = UEX_ROUTES_URL
) -> discord.Embed:
    """Render ranked trade routes as a Discord embed."""
    embed = discord.Embed(title="Top Trade Routes", url=url, color=ROUTE_COLOR)

    blocks = []
    if filters:
        blocks.append(f"**Filters:** {filters}")

    for index, route in enumerate(routes, start=1):
        header = f"**{index}. {route.commodity_name}** {_format_number(route.profit_per_scu, ' aUEC')}/SCU"
        leg = (
            f"{route.buy_terminal.name} ({route.buy_terminal.star_system_name}) "
            f"→ {route.sell_terminal.name} ({route.sell_terminal.star_system_name})"
        )
        lines = [header, leg]
        if route.total_profit is not None and route.scu is not None:
            investment = route.buy_price * route.scu
            sell_total = route.sell_price * route.scu
            lines.append(
                f"Invest {_format_number(investment, ' aUEC')} → "
                f"Sell {_format_number(sell_total, ' aUEC')} = "
                f"**{_format_number(route.total_profit, ' aUEC')}** profit/run · {route.scu:,} SCU"
            )
        blocks.append("\n".join(lines))

    embed.description = "\n\n".join(blocks)
    embed.add_field(
        name="More routes",
        value=f"[Open on UEX →]({url})",
        inline=False,
    )
    embed.set_footer(text="In-game aUEC prices via UEX · prices per SCU")
    return embed


def _name_choices(names) -> list[app_commands.Choice[str]]:
    choices: list[app_commands.Choice[str]] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        choices.append(app_commands.Choice(name=name[:100], value=name[:100]))
        if len(choices) >= 25:
            break
    return choices


def _route_filter_summary(
    *,
    ship: Optional[str],
    investment: Optional[int],
    scu: Optional[int],
    commodity: Optional[str],
    system_start: Optional[str],
    system_end: Optional[str],
    orbit_start: Optional[str],
    orbit_end: Optional[str],
    terminal_start: Optional[str],
    container: Optional[int],
    faction: Optional[str],
    toggles: Optional[list[str]] = None,
) -> Optional[str]:
    parts = []
    if commodity:
        parts.append(commodity)
    if ship:
        parts.append(f"Ship: {ship}")
    if scu:
        parts.append(f"{scu:,} SCU")
    if investment:
        parts.append(f"{investment:,} aUEC budget")
    if system_start:
        parts.append(f"From {system_start}")
    if system_end:
        parts.append(f"To {system_end}")
    if orbit_start:
        parts.append(f"From {orbit_start}")
    if orbit_end:
        parts.append(f"To {orbit_end}")
    if terminal_start:
        parts.append(f"Buy at {terminal_start}")
    if container:
        parts.append(f"{container} SCU containers")
    if faction:
        parts.append(faction)
    if toggles:
        parts.extend(toggles)
    return " · ".join(parts) if parts else None


class CommodityCog(commands.Cog):
    """Commodity buy/sell/route lookups against the UEX API."""

    commodity = app_commands.Group(name="commodity", description="Commodity trading commands")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def commodity_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Suggest commodity names as the user types, de-duplicated by name.

        Before anything is typed, show a default sample of commodities rather
        than an empty list.
        """
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
        return _name_choices(vehicle.name for vehicle in results)

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
        await self._respond(
            interaction, name, selling=False, system=system, place=place, exterior_cargo=exterior_cargo
        )

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
        await self._respond(
            interaction, name, selling=True, system=system, place=place, exterior_cargo=exterior_cargo
        )

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
        await interaction.response.defer()
        try:
            prices = await self.bot.commodity_prices_api.all()
            terminals = await self.bot.terminals_api.all(terminal_type="commodity")
        except UEXError as e:
            await interaction.followup.send(
                f"Couldn't reach the UEX API right now: {e}", ephemeral=True
            )
            return

        id_commodity = None
        commodity_name = None
        if commodity:
            try:
                match = await self.bot.commodities_api.find(commodity)
            except UEXError:
                match = None
            if match is None or match.id is None:
                await interaction.followup.send(
                    f"No commodity found matching **{commodity}**.", ephemeral=True
                )
                return
            id_commodity = match.id
            commodity_name = match.name

        vehicle = None
        if ship:
            try:
                vehicle = await self.bot.vehicles_api.find(ship)
            except UEXError:
                vehicle = None

        capacity = _capacity(vehicle, scu)
        container = container_size.value if container_size else None
        system_start = star_system_start.value if star_system_start else None
        system_end = star_system_end.value if star_system_end else None

        terminal_flags = {
            "has_loading_dock": has_loading_dock,
            "is_auto_load": is_auto_load,
            "is_nqa": is_nqa,
            "has_refuel": has_refuel,
            "is_player_owned": is_player_owned,
            "is_space_station": is_space_station,
        }
        origin = _terminal_predicate(
            system=system_start,
            orbit=orbit_start,
            terminal_name=terminal_start,
            faction=faction,
            container_size=container,
            **terminal_flags,
        )
        destination = _terminal_predicate(
            system=system_end,
            orbit=orbit_end,
            terminal_name=None,
            faction=faction,
            container_size=container,
            **terminal_flags,
        )

        allowed_commodities = None
        if safe_commodities:
            try:
                catalogue = await self.bot.commodities_api.all()
            except UEXError:
                catalogue = []
            allowed_commodities = {
                c.id for c in catalogue if c.id is not None and not c.is_illegal
            }

        terminals_by_id = {t.id: t for t in terminals if t.id is not None}
        routes = best_routes(
            prices,
            terminals_by_id,
            origin=origin,
            destination=destination,
            id_commodity=id_commodity,
            capacity=capacity,
            investment=investment,
            allowed_commodities=allowed_commodities,
        )
        if not routes:
            await interaction.followup.send(
                "No profitable routes match those filters.", ephemeral=True
            )
            return

        toggles = [
            label
            for label, value in (
                ("Loop", is_loop),
                ("Loading dock", has_loading_dock),
                ("Auto-load", is_auto_load),
                ("Legal only", safe_commodities),
                ("NQA", is_nqa),
                ("Monitored", is_monitored),
                ("Space station", is_space_station),
                ("Refuel", has_refuel),
                ("Predictable", is_predictable),
                ("Player-owned", is_player_owned),
            )
            if value
        ]
        filters = _route_filter_summary(
            ship=ship,
            investment=investment,
            scu=scu,
            commodity=commodity,
            system_start=system_start,
            system_end=system_end,
            orbit_start=orbit_start,
            orbit_end=orbit_end,
            terminal_start=terminal_start,
            container=container,
            faction=faction,
            toggles=toggles,
        )
        url = build_uex_url(
            {
                "id_vehicle": vehicle.id if vehicle else None,
                "investment": f"{investment:,}" if investment else None,
                "orbit_origin": _slugify(orbit_start) if orbit_start else None,
                "orbit_destination": _slugify(orbit_end) if orbit_end else None,
                "terminal_origin": _terminal_slug(terminals, terminal_start),
                "id_star_system_origin": _lookup_id(
                    terminals, lambda t: t.star_system_name, system_start, lambda t: t.id_star_system
                ),
                "id_star_system_destination": _lookup_id(
                    terminals, lambda t: t.star_system_name, system_end, lambda t: t.id_star_system
                ),
                "scu": scu,
                "commodity": _slugify(commodity_name) if commodity_name else None,
                "mcs": container,
                "id_faction": _lookup_id(
                    terminals, lambda t: t.faction_name, faction, lambda t: t.id_faction
                ),
                "is_loop": 1 if is_loop else None,
                "has_loading_dock": 1 if has_loading_dock else None,
                "is_auto_load": 1 if is_auto_load else None,
                "safe_commodities": 1 if safe_commodities else None,
                "is_nqa": 1 if is_nqa else None,
                "is_monitored": 1 if is_monitored else None,
                "is_space_station": 1 if is_space_station else None,
                "has_refuel": 1 if has_refuel else None,
                "is_predictable": 1 if is_predictable else None,
                "is_player_owned": 1 if is_player_owned else None,
            }
        )
        await interaction.followup.send(embed=build_routes_embed(routes, filters=filters, url=url))

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

        locations = _selling_locations(prices) if selling else _buying_locations(prices)
        filters = _commodity_filter_summary(system, place, exterior_cargo)
        await interaction.followup.send(
            embed=build_commodity_embed(
                commodity, locations, selling=selling, filters=filters, show_system=system is None
            )
        )

    async def _find_commodity(
        self, interaction: discord.Interaction, name: str
    ) -> Optional[Commodity]:
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
    ) -> Optional[list[CommodityPrice]]:
        try:
            prices = await self.bot.commodity_prices_api.for_commodity(commodity_id)
            if system is not None:
                target = system.value.lower()
                prices = [p for p in prices if (p.star_system_name or "").lower() == target]
            if place is not None:
                prices = [p for p in prices if _matches_place(p, place.value)]
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
        values = set()
        for terminal in terminals:
            value = getter(terminal)
            if value:
                values.add(value)
        needle = current.strip().lower()
        matches = [v for v in sorted(values) if not needle or needle in v.lower()]
        return _name_choices(matches)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommodityCog(bot))
