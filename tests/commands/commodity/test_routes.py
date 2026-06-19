"""Unit tests for src.commands.commodity.routes — _commodity_routes, best_routes."""

from src.commands.commodity.constants import MAX_ROUTES
from src.commands.commodity.routes import _commodity_routes, best_routes
from src.uex_api import CommodityPrice, Terminal


# ── Factories ─────────────────────────────────────────────────────────────────

def _terminal(id: int, name: str = "Terminal", system: str = "Stanton") -> Terminal:
    return Terminal.from_api({"id": str(id), "name": name, "star_system_name": system})


def _price(id_commodity: int, id_terminal: int, *, price_buy=None, price_sell=None,
           scu_buy=None, scu_sell=None, commodity_name: str = "Gold") -> CommodityPrice:
    return CommodityPrice.from_api({
        "id_commodity": str(id_commodity),
        "id_terminal": str(id_terminal),
        "price_buy": price_buy,
        "price_sell": price_sell,
        "scu_buy": scu_buy,
        "scu_sell": scu_sell,
        "commodity_name": commodity_name,
    })


def _buy_opt(terminal_id: int, buy_price: float, scu: float = 50.0) -> tuple:
    t = _terminal(terminal_id, f"Buy{terminal_id}")
    p = CommodityPrice.from_api({"price_buy": buy_price, "scu_buy": scu, "commodity_name": "Gold"})
    return (p, t)


def _sell_opt(terminal_id: int, sell_price: float, scu_sell: float = 50.0) -> tuple:
    t = _terminal(terminal_id, f"Sell{terminal_id}")
    p = CommodityPrice.from_api({"price_sell": sell_price, "scu_sell": scu_sell})
    return (p, t)


# ── _commodity_routes ─────────────────────────────────────────────────────────

class TestCommodityRoutes:
    def test_profitable_route_returned(self):
        routes = _commodity_routes([_buy_opt(1, 100.0)], [_sell_opt(2, 200.0)], None, None)
        assert len(routes) == 1

    def test_profit_per_scu_is_sell_minus_buy(self):
        routes = _commodity_routes([_buy_opt(1, 100.0)], [_sell_opt(2, 200.0)], None, None)
        assert routes[0].profit_per_scu == 100.0

    def test_unprofitable_route_excluded(self):
        routes = _commodity_routes([_buy_opt(1, 200.0)], [_sell_opt(2, 100.0)], None, None)
        assert routes == []

    def test_zero_profit_excluded(self):
        routes = _commodity_routes([_buy_opt(1, 150.0)], [_sell_opt(2, 150.0)], None, None)
        assert routes == []

    def test_same_terminal_excluded(self):
        t = _terminal(1)
        buy_p = CommodityPrice.from_api({"price_buy": 100.0, "scu_buy": 50.0})
        sell_p = CommodityPrice.from_api({"price_sell": 200.0})
        routes = _commodity_routes([(buy_p, t)], [(sell_p, t)], None, None)
        assert routes == []

    def test_capacity_caps_scu(self):
        routes = _commodity_routes([_buy_opt(1, 100.0, scu=100)], [_sell_opt(2, 200.0, scu_sell=100)], 32, None)
        assert routes[0].scu == 32

    def test_investment_caps_scu(self):
        # buy_price=100, investment=500 → max 5 SCU
        routes = _commodity_routes([_buy_opt(1, 100.0, scu=100)], [_sell_opt(2, 200.0, scu_sell=100)], None, 500)
        assert routes[0].scu == 5

    def test_scu_limited_by_buy_stock(self):
        routes = _commodity_routes([_buy_opt(1, 100.0, scu=3)], [_sell_opt(2, 200.0, scu_sell=100)], None, None)
        assert routes[0].scu == 3

    def test_scu_limited_by_sell_stock(self):
        routes = _commodity_routes([_buy_opt(1, 100.0, scu=100)], [_sell_opt(2, 200.0, scu_sell=4)], None, None)
        assert routes[0].scu == 4

    def test_total_profit_equals_profit_per_scu_times_scu(self):
        routes = _commodity_routes([_buy_opt(1, 100.0, scu=10)], [_sell_opt(2, 200.0, scu_sell=10)], None, None)
        r = routes[0]
        assert r.total_profit == r.profit_per_scu * r.scu

    def test_multiple_buy_sell_pairs_returned(self):
        buys = [_buy_opt(1, 100.0), _buy_opt(3, 110.0)]
        sells = [_sell_opt(2, 200.0), _sell_opt(4, 220.0)]
        routes = _commodity_routes(buys, sells, None, None)
        assert len(routes) == 4  # 2 buy × 2 sell, all profitable

    def test_commodity_name_from_buy_row(self):
        t_buy, t_sell = _terminal(1), _terminal(2)
        buy_p = CommodityPrice.from_api({"price_buy": 100.0, "scu_buy": 10.0, "commodity_name": "Laranite"})
        sell_p = CommodityPrice.from_api({"price_sell": 200.0})
        routes = _commodity_routes([(buy_p, t_buy)], [(sell_p, t_sell)], None, None)
        assert routes[0].commodity_name == "Laranite"


# ── best_routes ───────────────────────────────────────────────────────────────

def _setup_route(
    commodity_id: int = 1,
    buy_terminal_id: int = 1,
    sell_terminal_id: int = 2,
    buy_price: float = 100.0,
    sell_price: float = 200.0,
    scu_buy: float = 50.0,
    commodity_name: str = "Gold",
) -> tuple[list[CommodityPrice], dict[int, Terminal]]:
    buy_t = _terminal(buy_terminal_id, f"Buy{buy_terminal_id}")
    sell_t = _terminal(sell_terminal_id, f"Sell{sell_terminal_id}")
    prices = [
        _price(commodity_id, buy_terminal_id, price_buy=buy_price, scu_buy=scu_buy, commodity_name=commodity_name),
        _price(commodity_id, sell_terminal_id, price_sell=sell_price),
    ]
    terminals = {buy_t.id: buy_t, sell_t.id: sell_t}
    return prices, terminals


class TestBestRoutes:
    _ALWAYS = staticmethod(lambda t: True)
    _NEVER = staticmethod(lambda t: False)

    def test_profitable_route_returned(self):
        prices, terminals = _setup_route(buy_price=100.0, sell_price=200.0)
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        assert len(routes) == 1

    def test_unprofitable_route_excluded(self):
        prices, terminals = _setup_route(buy_price=200.0, sell_price=100.0)
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        assert routes == []

    def test_origin_predicate_filters_buy_terminal(self):
        prices, terminals = _setup_route()
        routes = best_routes(prices, terminals, origin=self._NEVER, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        assert routes == []

    def test_destination_predicate_filters_sell_terminal(self):
        prices, terminals = _setup_route()
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._NEVER,
                             id_commodity=None, capacity=None, investment=None)
        assert routes == []

    def test_commodity_id_filter_excludes_non_matching(self):
        prices, terminals = _setup_route(commodity_id=5)
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=99, capacity=None, investment=None)
        assert routes == []

    def test_commodity_id_filter_returns_matching(self):
        prices, terminals = _setup_route(commodity_id=5)
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=5, capacity=None, investment=None)
        assert len(routes) == 1

    def test_unknown_terminal_id_skipped(self):
        prices, _ = _setup_route()
        # Pass empty terminals_by_id so lookups always fail
        routes = best_routes(prices, {}, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        assert routes == []

    def test_missing_scu_buy_excludes_buy_row(self):
        buy_t = _terminal(1, "Buy")
        sell_t = _terminal(2, "Sell")
        prices = [
            # scu_buy=None → treated as 0 → excluded from buys
            _price(1, 1, price_buy=100.0, scu_buy=None),
            _price(1, 2, price_sell=200.0),
        ]
        terminals = {buy_t.id: buy_t, sell_t.id: sell_t}
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        assert routes == []

    def test_returns_at_most_max_routes(self):
        prices = []
        terminals = {}
        for i in range(MAX_ROUTES + 3):
            buy_t = _terminal(i * 2, f"Buy{i}")
            sell_t = _terminal(i * 2 + 1, f"Sell{i}")
            terminals[buy_t.id] = buy_t
            terminals[sell_t.id] = sell_t
            prices.append(_price(i + 100, i * 2, price_buy=100.0, scu_buy=50.0, commodity_name=f"Comm{i}"))
            prices.append(_price(i + 100, i * 2 + 1, price_sell=200.0))

        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        assert len(routes) <= MAX_ROUTES

    def test_routes_sorted_by_total_profit_descending(self):
        prices = []
        terminals = {}
        # Commodity 1: profit=50/SCU × 10 = 500 total
        buy_t1, sell_t1 = _terminal(10, "Buy1"), _terminal(11, "Sell1")
        terminals.update({buy_t1.id: buy_t1, sell_t1.id: sell_t1})
        prices += [
            _price(1, 10, price_buy=100.0, scu_buy=10.0, commodity_name="Cheap"),
            _price(1, 11, price_sell=150.0),
        ]
        # Commodity 2: profit=100/SCU × 10 = 1000 total
        buy_t2, sell_t2 = _terminal(20, "Buy2"), _terminal(21, "Sell2")
        terminals.update({buy_t2.id: buy_t2, sell_t2.id: sell_t2})
        prices += [
            _price(2, 20, price_buy=100.0, scu_buy=10.0, commodity_name="Profitable"),
            _price(2, 21, price_sell=200.0),
        ]

        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        assert routes[0].commodity_name == "Profitable"
        assert routes[0].total_profit >= routes[1].total_profit

    def test_id_commodity_none_returns_one_best_per_commodity(self):
        # Same commodity, two buy→sell pairs
        prices = []
        terminals = {}
        buy_t = _terminal(1, "BuyT")
        sell_t1 = _terminal(2, "SellT1")
        sell_t2 = _terminal(3, "SellT2")
        terminals.update({buy_t.id: buy_t, sell_t1.id: sell_t1, sell_t2.id: sell_t2})
        prices = [
            _price(1, 1, price_buy=100.0, scu_buy=10.0, commodity_name="Gold"),
            _price(1, 2, price_sell=200.0),
            _price(1, 3, price_sell=300.0),
        ]
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None)
        # When id_commodity=None, only best route per commodity
        assert len(routes) == 1
        assert routes[0].sell_price == 300.0

    def test_id_commodity_set_returns_all_viable_pairs(self):
        prices = []
        terminals = {}
        buy_t = _terminal(1, "BuyT")
        sell_t1 = _terminal(2, "SellT1")
        sell_t2 = _terminal(3, "SellT2")
        terminals.update({buy_t.id: buy_t, sell_t1.id: sell_t1, sell_t2.id: sell_t2})
        prices = [
            _price(1, 1, price_buy=100.0, scu_buy=10.0, commodity_name="Gold"),
            _price(1, 2, price_sell=200.0),
            _price(1, 3, price_sell=300.0),
        ]
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=1, capacity=None, investment=None)
        # When id_commodity=1, all pairs for that commodity
        assert len(routes) == 2

    def test_allowed_commodities_filter(self):
        prices, terminals = _setup_route(commodity_id=5)
        routes = best_routes(prices, terminals, origin=self._ALWAYS, destination=self._ALWAYS,
                             id_commodity=None, capacity=None, investment=None,
                             allowed_commodities={99})
        assert routes == []
