"""Unit tests for src.commands.commodity.helpers — all pure helper functions."""

from discord import app_commands

from src.commands.commodity.shared import (
    UEX_ROUTES_URL,
    build_uex_url,
    buying_locations,
    capacity,
    commodity_filter_summary,
    matches_place,
    route_filter_summary,
    selling_locations,
    slugify,
    terminal_predicate,
    tradeable_scu,
)
from src.uex_api.models import CommodityPrice, Terminal, Vehicle


def _price(**kwargs) -> CommodityPrice:
    return CommodityPrice.from_api(kwargs)


def _terminal(**kwargs) -> Terminal:
    return Terminal.from_api(kwargs)


def _vehicle(**kwargs) -> Vehicle:
    return Vehicle.from_api(kwargs)


def _choice(name: str, value: str | None = None) -> app_commands.Choice[str]:
    return app_commands.Choice(name=name, value=value or name)


class TestMatchesPlace:
    def test_space_station_matches_station(self):
        p = _price(space_station_name="CRU-L1")
        assert matches_place(p, "station")

    def test_outpost_matches_outpost(self):
        p = _price(outpost_name="Shubin Mining SA-1")
        assert matches_place(p, "outpost")

    def test_city_matches_planet(self):
        p = _price(city_name="Lorville")
        assert matches_place(p, "planet")

    def test_planet_matches_planet(self):
        p = _price(planet_name="Hurston")
        assert matches_place(p, "planet")

    def test_station_does_not_match_planet(self):
        p = _price(space_station_name="CRU-L1")
        assert not matches_place(p, "planet")

    def test_outpost_does_not_match_station(self):
        p = _price(outpost_name="Mining Post")
        assert not matches_place(p, "station")


class TestBuyingLocations:
    def test_excludes_rows_without_buy_price(self):
        prices = [_price(price_sell=100.0), _price(price_buy=50.0)]
        assert len(buying_locations(prices)) == 1

    def test_sorted_cheapest_first(self):
        prices = [_price(price_buy=200.0), _price(price_buy=50.0), _price(price_buy=150.0)]
        result = buying_locations(prices)
        assert [p.price_buy for p in result] == [50.0, 150.0, 200.0]

    def test_empty_input_returns_empty(self):
        assert buying_locations([]) == []


class TestSellingLocations:
    def test_excludes_rows_without_sell_price(self):
        prices = [_price(price_buy=50.0), _price(price_sell=200.0)]
        assert len(selling_locations(prices)) == 1

    def test_sorted_highest_payout_first(self):
        prices = [_price(price_sell=100.0), _price(price_sell=300.0), _price(price_sell=200.0)]
        result = selling_locations(prices)
        assert [p.price_sell for p in result] == [300.0, 200.0, 100.0]

    def test_empty_input_returns_empty(self):
        assert selling_locations([]) == []


class TestTradeableScu:
    def test_capped_by_scu_buy(self):
        assert tradeable_scu(10.0, 5.0, 100.0, None, None) == 5

    def test_capped_by_scu_sell(self):
        assert tradeable_scu(10.0, 100.0, 8.0, None, None) == 8

    def test_capped_by_capacity(self):
        assert tradeable_scu(10.0, 100.0, 100.0, 32, None) == 32

    def test_capped_by_investment(self):
        assert tradeable_scu(100.0, 1000.0, 1000.0, None, 500) == 5

    def test_minimum_of_all_caps(self):
        assert tradeable_scu(100.0, 50.0, 30.0, 10, 2000) == 10

    def test_zero_scu_sell_is_ignored(self):
        # scu_sell=0 should not act as a cap
        assert tradeable_scu(10.0, 20.0, 0.0, None, None) == 20


class TestCapacity:
    def test_no_vehicle_no_scu_returns_none(self):
        assert capacity(None, None) is None

    def test_vehicle_scu_used_when_only_cap(self):
        v = _vehicle(scu=48.0)
        assert capacity(v, None) == 48

    def test_explicit_scu_used_when_no_vehicle(self):
        assert capacity(None, 16) == 16

    def test_takes_minimum_of_vehicle_and_scu(self):
        v = _vehicle(scu=48.0)
        assert capacity(v, 16) == 16

    def test_vehicle_is_minimum_when_scu_is_larger(self):
        v = _vehicle(scu=8.0)
        assert capacity(v, 32) == 8


class TestSlugify:
    def test_lowercases_input(self):
        assert slugify("Lorville") == "lorville"

    def test_spaces_become_hyphens(self):
        assert slugify("New Babbage") == "new-babbage"

    def test_special_characters_removed(self):
        assert slugify("GrimHEX!") == "grimhex"

    def test_strips_leading_trailing_hyphens(self):
        assert slugify("--foo--") == "foo"

    def test_already_clean_passthrough(self):
        assert slugify("stanton") == "stanton"


class TestCommodityFilterSummary:
    def test_no_filters_returns_none(self):
        assert commodity_filter_summary(None, None, None) is None

    def test_system_only(self):
        assert commodity_filter_summary(_choice("Stanton"), None, None) == "Stanton"

    def test_exterior_cargo_true(self):
        assert commodity_filter_summary(None, None, True) == "Exterior cargo"

    def test_exterior_cargo_false(self):
        assert commodity_filter_summary(None, None, False) == "No exterior cargo"

    def test_system_and_place_joined_with_separator(self):
        result = commodity_filter_summary(_choice("Stanton"), _choice("Station", "station"), None)
        assert result == "Stanton · Station"

    def test_all_three_filters(self):
        result = commodity_filter_summary(_choice("Pyro"), _choice("Outpost", "outpost"), True)
        assert result == "Pyro · Outpost · Exterior cargo"


class TestRouteFilterSummary:
    _empty = dict(
        ship=None, investment=None, scu=None, commodity=None,
        system_start=None, system_end=None, orbit_start=None,
        orbit_end=None, terminal_start=None, container=None, faction=None,
    )

    def test_all_none_returns_none(self):
        assert route_filter_summary(**self._empty) is None

    def test_commodity_only(self):
        assert route_filter_summary(**{**self._empty, "commodity": "Gold"}) == "Gold"

    def test_ship_prefixed(self):
        result = route_filter_summary(**{**self._empty, "ship": "Cutlass Black"})
        assert result == "Ship: Cutlass Black"

    def test_investment_formatted_with_thousands(self):
        result = route_filter_summary(**{**self._empty, "investment": 10_000})
        assert "10,000 aUEC budget" in result

    def test_system_start_prefixed(self):
        result = route_filter_summary(**{**self._empty, "system_start": "Stanton"})
        assert "From Stanton" in result

    def test_multiple_fields_joined_with_separator(self):
        result = route_filter_summary(
            **{**self._empty, "commodity": "Laranite", "system_start": "Stanton"}
        )
        assert "Laranite" in result
        assert "From Stanton" in result
        assert " · " in result


class TestTerminalPredicate:
    def test_no_filters_matches_any_terminal(self):
        t = _terminal(name="Any Terminal")
        pred = terminal_predicate(system=None, orbit=None, terminal_name=None, faction=None, container_size=None)
        assert pred(t)

    def test_system_filter_matches(self):
        t = _terminal(star_system_name="Stanton")
        pred = terminal_predicate(system="Stanton", orbit=None, terminal_name=None, faction=None, container_size=None)
        assert pred(t)

    def test_system_filter_is_case_insensitive(self):
        t = _terminal(star_system_name="Stanton")
        pred = terminal_predicate(system="stanton", orbit=None, terminal_name=None, faction=None, container_size=None)
        assert pred(t)

    def test_system_filter_rejects_mismatch(self):
        t = _terminal(star_system_name="Pyro")
        pred = terminal_predicate(system="Stanton", orbit=None, terminal_name=None, faction=None, container_size=None)
        assert not pred(t)

    def test_container_size_passes_when_large_enough(self):
        t = _terminal(max_container_size=32)
        pred = terminal_predicate(system=None, orbit=None, terminal_name=None, faction=None, container_size=16)
        assert pred(t)

    def test_container_size_rejects_when_too_small(self):
        t = _terminal(max_container_size=8)
        pred = terminal_predicate(system=None, orbit=None, terminal_name=None, faction=None, container_size=16)
        assert not pred(t)

    def test_terminal_name_is_substring_match(self):
        t = _terminal(name="Refinery Desk Alpha")
        pred = terminal_predicate(system=None, orbit=None, terminal_name="Refinery", faction=None, container_size=None)
        assert pred(t)

    def test_faction_filter_matches(self):
        t = _terminal(faction_name="Xenothreat")
        pred = terminal_predicate(system=None, orbit=None, terminal_name=None, faction="Xenothreat", container_size=None)
        assert pred(t)


class TestBuildUexUrl:
    def test_no_params_returns_base_url(self):
        assert build_uex_url({}) == UEX_ROUTES_URL

    def test_none_values_are_excluded(self):
        result = build_uex_url({"system": "Stanton", "faction": None})
        assert "system=Stanton" in result
        assert "faction" not in result

    def test_params_appear_as_query_string(self):
        result = build_uex_url({"commodity": "Gold"})
        assert "commodity=Gold" in result
        assert "?" in result
