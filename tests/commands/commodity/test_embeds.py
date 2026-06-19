"""Unit tests for src.commands.commodity.embeds — three embed builders."""

from src.commands.commodity.shared import (
    BUY_COLOR,
    LOSS_COLOR,
    MAX_LOCATIONS_SHOWN,
    ROUTE_COLOR,
    SELL_COLOR,
    Route,
    build_commodity_embed,
    build_routes_embed,
    build_trade_embed,
)
from src.uex_api import Commodity, CommodityPrice, Terminal

# ── Factories ─────────────────────────────────────────────────────────────────

def _commodity(name: str = "Gold") -> Commodity:
    return Commodity.from_api({"name": name, "id": "1"})


def _cp(price_buy=None, price_sell=None, terminal_name="Outpost Alpha", system="Stanton") -> CommodityPrice:
    return CommodityPrice.from_api({
        "price_buy": price_buy,
        "price_sell": price_sell,
        "terminal_name": terminal_name,
        "star_system_name": system,
    })


def _terminal(id: int = 1, name: str = "TDD", system: str = "Stanton") -> Terminal:
    return Terminal.from_api({"id": str(id), "name": name, "star_system_name": system})


def _route(commodity: str = "Gold", buy_price: float = 100.0, sell_price: float = 200.0, scu: int = 10) -> Route:
    profit = sell_price - buy_price
    return Route(
        commodity_name=commodity,
        buy_terminal=_terminal(1, "Buy Station", "Stanton"),
        sell_terminal=_terminal(2, "Sell Outpost", "Pyro"),
        buy_price=buy_price,
        sell_price=sell_price,
        profit_per_scu=profit,
        scu=scu,
        total_profit=profit * scu,
    )


# ── build_commodity_embed ─────────────────────────────────────────────────────

class TestBuildCommodityEmbed:
    def test_title_includes_commodity_and_action_buy(self):
        embed = build_commodity_embed(_commodity("Laranite"), [], selling=False)
        assert "Laranite" in embed.title
        assert "Buy" in embed.title

    def test_title_includes_commodity_and_action_sell(self):
        embed = build_commodity_embed(_commodity("Laranite"), [], selling=True)
        assert "Laranite" in embed.title
        assert "Sell" in embed.title

    def test_buy_color(self):
        embed = build_commodity_embed(_commodity(), [], selling=False)
        assert embed.color.value == BUY_COLOR

    def test_sell_color(self):
        embed = build_commodity_embed(_commodity(), [], selling=True)
        assert embed.color.value == SELL_COLOR

    def test_no_locations_shows_not_found_message(self):
        embed = build_commodity_embed(_commodity(), [], selling=False)
        assert any("No matching terminals found" in f.value for f in embed.fields)

    def test_locations_shown_in_field(self):
        prices = [_cp(price_buy=100.0)]
        embed = build_commodity_embed(_commodity(), prices, selling=False)
        field_values = " ".join(f.value for f in embed.fields)
        assert "Outpost Alpha" in field_values

    def test_overflow_message_shown_when_more_than_limit(self):
        prices = [_cp(price_buy=float(i)) for i in range(MAX_LOCATIONS_SHOWN + 2)]
        embed = build_commodity_embed(_commodity(), prices, selling=False)
        field_values = " ".join(f.value for f in embed.fields)
        assert "more terminal" in field_values

    def test_no_overflow_message_at_limit(self):
        prices = [_cp(price_buy=float(i)) for i in range(MAX_LOCATIONS_SHOWN)]
        embed = build_commodity_embed(_commodity(), prices, selling=False)
        field_values = " ".join(f.value for f in embed.fields)
        assert "more terminal" not in field_values

    def test_filters_shown_in_description(self):
        embed = build_commodity_embed(_commodity(), [], selling=False, filters="Stanton")
        assert embed.description and "Stanton" in embed.description

    def test_no_description_without_filters(self):
        embed = build_commodity_embed(_commodity(), [], selling=False)
        assert not embed.description

    def test_footer_has_source_attribution(self):
        embed = build_commodity_embed(_commodity(), [], selling=False)
        assert "UEX" in embed.footer.text

    def test_system_hidden_when_show_system_false(self):
        prices = [_cp(price_buy=100.0, system="Stanton")]
        embed = build_commodity_embed(_commodity(), prices, selling=False, show_system=False)
        field_values = " ".join(f.value for f in embed.fields)
        assert "Stanton" not in field_values


# ── build_trade_embed ─────────────────────────────────────────────────────────

class TestBuildTradeEmbed:
    def test_title_includes_commodity_and_trade_route(self):
        embed = build_trade_embed(_commodity("Titanium"), _cp(price_buy=100.0), _cp(price_sell=200.0))
        assert "Titanium" in embed.title
        assert "Trade Route" in embed.title

    def test_profitable_trade_uses_buy_color(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=100.0), _cp(price_sell=200.0))
        assert embed.color.value == BUY_COLOR

    def test_loss_trade_uses_loss_color(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=200.0), _cp(price_sell=100.0))
        assert embed.color.value == LOSS_COLOR

    def test_has_buy_field(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=100.0), _cp(price_sell=200.0))
        field_names = [f.name for f in embed.fields]
        assert "Buy" in field_names

    def test_has_sell_field(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=100.0), _cp(price_sell=200.0))
        field_names = [f.name for f in embed.fields]
        assert "Sell" in field_names

    def test_has_profit_field(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=100.0), _cp(price_sell=200.0))
        field_names = [f.name for f in embed.fields]
        assert "Profit" in field_names

    def test_profit_field_shows_roi_when_buy_price_set(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=100.0), _cp(price_sell=200.0))
        profit_field = next(f for f in embed.fields if f.name == "Profit")
        assert "ROI" in profit_field.value

    def test_profit_field_no_roi_when_no_buy_price(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=None), _cp(price_sell=200.0))
        profit_field = next(f for f in embed.fields if f.name == "Profit")
        assert "ROI" not in profit_field.value

    def test_filters_in_description(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=100.0), _cp(price_sell=200.0), filters="Pyro")
        assert embed.description and "Pyro" in embed.description

    def test_footer_has_source_attribution(self):
        embed = build_trade_embed(_commodity(), _cp(price_buy=100.0), _cp(price_sell=200.0))
        assert "UEX" in embed.footer.text


# ── build_routes_embed ────────────────────────────────────────────────────────

class TestBuildRoutesEmbed:
    _URL = "https://uexcorp.space/trade/routes"

    def test_title_is_top_trade_routes(self):
        embed = build_routes_embed([], filters=None, url=self._URL)
        assert embed.title == "Top Trade Routes"

    def test_color_is_route_color(self):
        embed = build_routes_embed([], filters=None, url=self._URL)
        assert embed.color.value == ROUTE_COLOR

    def test_url_on_embed(self):
        embed = build_routes_embed([], filters=None, url=self._URL)
        assert embed.url == self._URL

    def test_route_commodity_name_in_description(self):
        embed = build_routes_embed([_route("Laranite")], filters=None, url=self._URL)
        assert "Laranite" in embed.description

    def test_route_terminals_in_description(self):
        embed = build_routes_embed([_route()], filters=None, url=self._URL)
        assert "Buy Station" in embed.description
        assert "Sell Outpost" in embed.description

    def test_route_systems_in_description(self):
        embed = build_routes_embed([_route()], filters=None, url=self._URL)
        assert "Stanton" in embed.description
        assert "Pyro" in embed.description

    def test_route_invest_sell_profit_line_present(self):
        embed = build_routes_embed([_route(buy_price=100.0, sell_price=200.0, scu=10)], filters=None, url=self._URL)
        assert "Invest" in embed.description
        assert "Sell" in embed.description
        assert "profit/run" in embed.description

    def test_filters_in_description(self):
        embed = build_routes_embed([_route()], filters="Stanton", url=self._URL)
        assert "Stanton" in embed.description
        assert "Filters" in embed.description

    def test_more_routes_field_with_url(self):
        embed = build_routes_embed([_route()], filters=None, url=self._URL)
        field_names = [f.name for f in embed.fields]
        assert "More routes" in field_names

    def test_route_ranked_with_index(self):
        routes = [_route("Gold"), _route("Laranite")]
        embed = build_routes_embed(routes, filters=None, url=self._URL)
        assert "**1." in embed.description
        assert "**2." in embed.description

    def test_footer_has_source_attribution(self):
        embed = build_routes_embed([], filters=None, url=self._URL)
        assert "UEX" in embed.footer.text
