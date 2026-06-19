"""Route-finding logic for /commodity route."""

from __future__ import annotations

from src.uex_api import CommodityPrice, Terminal

from .constants import MAX_ROUTES
from .helpers import Route, TerminalPredicate, tradeable_scu


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
    """Best buy→sell route per commodity, ranked by trip profit, capped at MAX_ROUTES.

    Only terminals with real supply (``scu_buy``) are considered, and each
    candidate pair's haul is limited by stock, ship hold, and budget.
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
        if id_commodity is None:
            routes.append(pairs[0])  # one best route per commodity in the global top-N
        else:
            routes.extend(pairs)  # all viable pairs when a specific commodity is requested

    routes.sort(key=lambda r: r.total_profit or 0.0, reverse=True)
    return routes[:MAX_ROUTES]


def _commodity_routes(
    buy_options: list[tuple[CommodityPrice, Terminal]],
    sell_options: list[tuple[CommodityPrice, Terminal]],
    capacity: int | None,
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
