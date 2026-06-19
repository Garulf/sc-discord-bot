"""Embed builders for /commodity subcommands."""
from __future__ import annotations

from typing import Optional

import discord

from src.uex_api import Commodity, CommodityPrice
from .constants import BUY_COLOR, LOSS_COLOR, MAX_LOCATIONS_SHOWN, ROUTE_COLOR, SELL_COLOR
from .helpers import Route, format_number, location_line, route_leg


def build_commodity_embed(
    commodity: Commodity,
    locations: list[CommodityPrice],
    *,
    selling: bool,
    filters: Optional[str] = None,
    show_system: bool = True,
) -> discord.Embed:
    """Best buy/sell terminals for a commodity."""
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
    filters: Optional[str] = None,
    show_system: bool = True,
) -> discord.Embed:
    """Best buy→sell route for a single commodity."""
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


def build_routes_embed(
    routes: list[Route], *, filters: Optional[str], url: str
) -> discord.Embed:
    """Ranked multi-commodity trade routes."""
    embed = discord.Embed(title="Top Trade Routes", url=url, color=ROUTE_COLOR)
    blocks = []
    if filters:
        blocks.append(f"**Filters:** {filters}")

    for index, route in enumerate(routes, start=1):
        header = (
            f"**{index}. {route.commodity_name}** "
            f"{format_number(route.profit_per_scu, ' aUEC')}/SCU"
        )
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
