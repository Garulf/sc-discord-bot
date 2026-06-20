"""Shared code for the /commodity command group.

Contains constants, pure helpers, embed builders, the buy/sell pipeline, and
autocomplete callbacks — everything used by more than one subcommand.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

import discord
from discord import app_commands

from src.commands.autocomplete import name_choices
from src.commands.formatting import format_number as _format_number_opt
from src.uex_api import Commodity, CommodityPrice, Terminal, UEXError, Vehicle

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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
CONTAINER_CHOICES = [app_commands.Choice(name=f"{size} SCU", value=size) for size in (1, 2, 4, 8, 16, 24, 32)]

# ---------------------------------------------------------------------------
# Pure helpers and data types
# ---------------------------------------------------------------------------

TerminalPredicate = Callable[[Terminal], bool]


def format_number(value: float | None, suffix: str = "") -> str:
    return _format_number_opt(value, suffix) or "?"


@dataclass(frozen=True)
class Route:
    commodity_name: str
    buy_terminal: Terminal
    sell_terminal: Terminal
    buy_price: float
    sell_price: float
    profit_per_scu: float
    scu: int | None
    total_profit: float | None


def matches_place(price: CommodityPrice, place: str) -> bool:
    if place == "planet":
        return price.place_type in ("planet", "city")
    return price.place_type == place


def buying_locations(prices: list[CommodityPrice]) -> list[CommodityPrice]:
    priced = [p for p in prices if p.price_buy]
    priced.sort(key=lambda p: p.price_buy or float("inf"))
    return priced


def selling_locations(prices: list[CommodityPrice]) -> list[CommodityPrice]:
    priced = [p for p in prices if p.price_sell]
    priced.sort(key=lambda p: p.price_sell or 0.0, reverse=True)
    return priced


def commodity_filter_summary(
    system: app_commands.Choice[str] | None,
    place: app_commands.Choice[str] | None,
    exterior_cargo: bool | None,
) -> str | None:
    parts = []
    if system is not None:
        parts.append(system.name)
    if place is not None:
        parts.append(place.name)
    if exterior_cargo is not None:
        parts.append("Exterior cargo" if exterior_cargo else "No exterior cargo")
    return " · ".join(parts) if parts else None


def location_line(price: CommodityPrice, value: float | None, *, show_system: bool) -> str:
    auec = format_number(value, " aUEC")
    suffix = f" ({price.star_system_name})" if show_system and price.star_system_name else ""
    return f"**{auec}** — {price.terminal_name or 'Unknown terminal'}{suffix}"


def route_leg(price: CommodityPrice, value: float | None, *, show_system: bool) -> str:
    auec = format_number(value, " aUEC")
    location = price.terminal_name or "Unknown terminal"
    if show_system and price.star_system_name:
        location += f" ({price.star_system_name})"
    return f"**{auec}**\n{location}"


def route_filter_summary(
    *,
    ship: str | None,
    investment: int | None,
    scu: int | None,
    commodity: str | None,
    system_start: str | None,
    system_end: str | None,
    orbit_start: str | None,
    orbit_end: str | None,
    terminal_start: str | None,
    container: int | None,
    faction: str | None,
    toggles: list[str] | None = None,
) -> str | None:
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


def terminal_predicate(
    *,
    system: str | None,
    orbit: str | None,
    terminal_name: str | None,
    faction: str | None,
    container_size: int | None,
    has_loading_dock: bool | None = None,
    is_auto_load: bool | None = None,
    is_nqa: bool | None = None,
    has_refuel: bool | None = None,
    is_player_owned: bool | None = None,
    is_space_station: bool | None = None,
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


def tradeable_scu(
    buy_price: float,
    scu_buy: float,
    scu_sell: float,
    capacity: int | None,
    investment: int | None,
) -> int:
    caps: list[float] = [scu_buy]
    if scu_sell > 0:
        caps.append(scu_sell)
    if capacity is not None:
        caps.append(capacity)
    if investment is not None and buy_price:
        caps.append(investment / buy_price)
    return int(min(caps))


def capacity(vehicle: Vehicle | None, scu: int | None) -> int | None:
    caps = []
    if vehicle is not None and vehicle.scu:
        caps.append(int(vehicle.scu))
    if scu:
        caps.append(scu)
    return min(caps) if caps else None


def lookup_id(
    terminals: list[Terminal],
    getter: Callable[[Terminal], str | None],
    value: str | None,
    id_getter: Callable[[Terminal], int | None],
) -> int | None:
    if not value:
        return None
    target = value.lower()
    for terminal in terminals:
        name = getter(terminal)
        if name and name.lower() == target:
            return id_getter(terminal)
    return None


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def terminal_slug(terminals: list[Terminal], value: str | None) -> str | None:
    if not value:
        return None
    target = value.lower()
    for terminal in terminals:
        if target in (terminal.name or "").lower():
            return slugify(terminal.name or "")
    return None


def build_uex_url(params: dict[str, object]) -> str:
    query = {key: value for key, value in params.items() if value is not None}
    if not query:
        return UEX_ROUTES_URL
    return f"{UEX_ROUTES_URL}?{urlencode(query)}"


# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------


def build_commodity_embed(
    commodity: Commodity,
    locations: list[CommodityPrice],
    *,
    selling: bool,
    filters: str | None = None,
    show_system: bool = True,
) -> discord.Embed:
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
        lines.append(location_line(price, value, show_system=show_system))
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
    filters: str | None = None,
    show_system: bool = True,
) -> discord.Embed:
    profit = (sell.price_sell or 0.0) - (buy.price_buy or 0.0)
    embed = discord.Embed(
        title=f"{commodity.name} — Best Trade Route",
        color=BUY_COLOR if profit > 0 else LOSS_COLOR,
    )
    if filters:
        embed.description = f"Filters: {filters}"

    embed.add_field(name="Buy", value=route_leg(buy, buy.price_buy, show_system=show_system), inline=True)
    embed.add_field(name="Sell", value=route_leg(sell, sell.price_sell, show_system=show_system), inline=True)

    summary = f"**{format_number(profit, ' aUEC')}** / unit"
    if buy.price_buy:
        roi = profit / buy.price_buy * 100
        summary += f"\n{format_number(roi)}% ROI"
    embed.add_field(name="Profit", value=summary, inline=True)
    embed.set_footer(text="In-game aUEC prices via UEX · per unit")
    return embed


def build_routes_embed(routes: list[Route], *, filters: str | None, url: str) -> discord.Embed:
    embed = discord.Embed(title="Top Trade Routes", url=url, color=ROUTE_COLOR)
    blocks = []
    if filters:
        blocks.append(f"**Filters:** {filters}")

    for index, route in enumerate(routes, start=1):
        header = f"**{index}. {route.commodity_name}** {format_number(route.profit_per_scu, ' aUEC')}/SCU"
        leg = (
            f"{route.buy_terminal.name} ({route.buy_terminal.star_system_name}) "
            f"→ {route.sell_terminal.name} ({route.sell_terminal.star_system_name})"
        )
        lines = [header, leg]
        if route.total_profit is not None and route.scu is not None:
            investment = route.buy_price * route.scu
            sell_total = route.sell_price * route.scu
            lines.append(
                f"Invest {format_number(investment, ' aUEC')} → "
                f"Sell {format_number(sell_total, ' aUEC')} = "
                f"**{format_number(route.total_profit, ' aUEC')}** profit/run · {route.scu:,} SCU"
            )
        blocks.append("\n".join(lines))

    embed.description = "\n\n".join(blocks)
    embed.add_field(name="More routes", value=f"[Open on UEX →]({url})", inline=False)
    embed.set_footer(text="In-game aUEC prices via UEX · prices per SCU")
    return embed


# ---------------------------------------------------------------------------
# Buy/sell pipeline (shared by buy.py and sell.py)
# ---------------------------------------------------------------------------


async def respond(
    cog,
    interaction: discord.Interaction,
    name: str,
    *,
    selling: bool,
    system: app_commands.Choice[str] | None,
    place: app_commands.Choice[str] | None,
    exterior_cargo: bool | None,
) -> None:
    await interaction.response.defer()
    commodity = await _find_commodity(cog, interaction, name)
    if commodity is None:
        return
    prices = await _collect_prices(
        cog, interaction, commodity.id, system=system, place=place, exterior_cargo=exterior_cargo
    )
    if prices is None:
        return
    locations = selling_locations(prices) if selling else buying_locations(prices)
    filters = commodity_filter_summary(system, place, exterior_cargo)
    await interaction.followup.send(
        embed=build_commodity_embed(commodity, locations, selling=selling, filters=filters, show_system=system is None)
    )


async def _find_commodity(cog, interaction: discord.Interaction, name: str):
    try:
        commodity = await cog.bot.commodities_api.find(name)
    except UEXError as e:
        await interaction.followup.send(f"Couldn't reach the UEX API right now: {e}", ephemeral=True)
        return None
    if commodity is None or commodity.id is None:
        await interaction.followup.send(f"No commodity found matching **{name}**.", ephemeral=True)
        return None
    return commodity


async def _collect_prices(
    cog,
    interaction: discord.Interaction,
    commodity_id: int,
    *,
    system: app_commands.Choice[str] | None,
    place: app_commands.Choice[str] | None,
    exterior_cargo: bool | None,
):
    try:
        prices = await cog.bot.commodity_prices_api.for_commodity(commodity_id)
        if system is not None:
            target = system.value.lower()
            prices = [p for p in prices if (p.star_system_name or "").lower() == target]
        if place is not None:
            prices = [p for p in prices if matches_place(p, place.value)]
        if exterior_cargo is not None:
            docks = await _exterior_terminal_ids(cog)
            prices = [p for p in prices if (p.id_terminal in docks) == exterior_cargo]
        return prices
    except UEXError as e:
        await interaction.followup.send(f"Couldn't reach the UEX API right now: {e}", ephemeral=True)
        return None


async def _exterior_terminal_ids(cog) -> set[int]:
    terminals = await cog.bot.terminals_api.all(terminal_type="commodity")
    return {t.id for t in terminals if t.has_loading_dock and t.id is not None}


# ---------------------------------------------------------------------------
# Autocomplete callbacks
# ---------------------------------------------------------------------------


async def autocomplete_commodity(cog, current: str) -> list[app_commands.Choice[str]]:
    try:
        if current:
            results = await cog.bot.commodities_api.search(current, limit=25)
        else:
            results = sorted(await cog.bot.commodities_api.all(), key=lambda c: c.name)
    except UEXError:
        return []
    return name_choices(item.name for item in results)


async def autocomplete_ship(cog, current: str) -> list[app_commands.Choice[str]]:
    try:
        if current:
            results = await cog.bot.vehicles_api.search(current, limit=25)
        else:
            results = sorted(await cog.bot.vehicles_api.all(), key=lambda v: v.name)
    except UEXError:
        return []
    return name_choices(vehicle.name for vehicle in results)


async def autocomplete_orbit(cog, current: str) -> list[app_commands.Choice[str]]:
    return await _terminal_attr_choices(cog, lambda t: t.orbit_name, current)


async def autocomplete_terminal(cog, current: str) -> list[app_commands.Choice[str]]:
    return await _terminal_attr_choices(cog, lambda t: t.name, current)


async def autocomplete_faction(cog, current: str) -> list[app_commands.Choice[str]]:
    return await _terminal_attr_choices(cog, lambda t: t.faction_name, current)


async def _terminal_attr_choices(
    cog, getter: Callable[[Terminal], str | None], current: str
) -> list[app_commands.Choice[str]]:
    try:
        terminals = await cog.bot.terminals_api.all(terminal_type="commodity")
    except UEXError:
        return []
    values = {getter(t) for t in terminals if getter(t)}
    needle = current.strip().lower()
    matches = [v for v in sorted(values) if not needle or needle in v.lower()]
    return name_choices(matches)
