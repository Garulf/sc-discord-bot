"""Pure helpers and data types for the /commodity command group."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlencode

from discord import app_commands

from src.commands.formatting import format_number as _format_number_opt
from src.uex_api import CommodityPrice, Terminal, Vehicle

from .constants import UEX_ROUTES_URL

TerminalPredicate = Callable[[Terminal], bool]


def format_number(value: float | None, suffix: str = "") -> str:
    """Format a number for display, returning '?' when the value is absent."""
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
    """Whether a price row's terminal matches a requested place type."""
    if place == "planet":
        return price.place_type in ("planet", "city")
    return price.place_type == place


def buying_locations(prices: list[CommodityPrice]) -> list[CommodityPrice]:
    """Terminals selling the commodity, cheapest first."""
    priced = [p for p in prices if p.price_buy]
    priced.sort(key=lambda p: p.price_buy or float("inf"))
    return priced


def selling_locations(prices: list[CommodityPrice]) -> list[CommodityPrice]:
    """Terminals buying the commodity, highest payout first."""
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
    """SCU actually movable: limited by supply, ship hold, and budget."""
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
    """Build a UEX deep link carrying the provided filters as query params."""
    query = {key: value for key, value in params.items() if value is not None}
    if not query:
        return UEX_ROUTES_URL
    return f"{UEX_ROUTES_URL}?{urlencode(query)}"
