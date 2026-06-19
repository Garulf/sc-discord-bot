"""Handler for /commodity route."""
from __future__ import annotations
from typing import Optional

import discord
from discord import app_commands

from src.uex_api import UEXError
from .embeds import build_routes_embed
from .helpers import (
    build_uex_url,
    capacity,
    lookup_id,
    route_filter_summary,
    slugify,
    terminal_predicate,
    terminal_slug,
)
from .routes import best_routes


async def handle(
    cog,
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
) -> None:
    await interaction.response.defer()
    try:
        prices = await cog.bot.commodity_prices_api.all()
        terminals = await cog.bot.terminals_api.all(terminal_type="commodity")
    except UEXError as e:
        await interaction.followup.send(f"Couldn't reach the UEX API right now: {e}", ephemeral=True)
        return

    id_commodity = None
    commodity_name = None
    if commodity:
        try:
            match = await cog.bot.commodities_api.find(commodity)
        except UEXError:
            match = None
        if match is None or match.id is None:
            await interaction.followup.send(f"No commodity found matching **{commodity}**.", ephemeral=True)
            return
        id_commodity = match.id
        commodity_name = match.name

    vehicle = None
    if ship:
        try:
            vehicle = await cog.bot.vehicles_api.find(ship)
        except UEXError:
            vehicle = None

    cap = capacity(vehicle, scu)
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
    origin = terminal_predicate(
        system=system_start,
        orbit=orbit_start,
        terminal_name=terminal_start,
        faction=faction,
        container_size=container,
        **terminal_flags,
    )
    destination = terminal_predicate(
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
            catalogue = await cog.bot.commodities_api.all()
        except UEXError:
            catalogue = []
        allowed_commodities = {c.id for c in catalogue if c.id is not None and not c.is_illegal}

    terminals_by_id = {t.id: t for t in terminals if t.id is not None}
    found_routes = best_routes(
        prices,
        terminals_by_id,
        origin=origin,
        destination=destination,
        id_commodity=id_commodity,
        capacity=cap,
        investment=investment,
        allowed_commodities=allowed_commodities,
    )
    if not found_routes:
        await interaction.followup.send("No profitable routes match those filters.", ephemeral=True)
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
    filters = route_filter_summary(
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
            "orbit_origin": slugify(orbit_start) if orbit_start else None,
            "orbit_destination": slugify(orbit_end) if orbit_end else None,
            "terminal_origin": terminal_slug(terminals, terminal_start),
            "id_star_system_origin": lookup_id(
                terminals, lambda t: t.star_system_name, system_start, lambda t: t.id_star_system
            ),
            "id_star_system_destination": lookup_id(
                terminals, lambda t: t.star_system_name, system_end, lambda t: t.id_star_system
            ),
            "scu": scu,
            "commodity": slugify(commodity_name) if commodity_name else None,
            "mcs": container,
            "id_faction": lookup_id(
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
    await interaction.followup.send(embed=build_routes_embed(found_routes, filters=filters, url=url))
