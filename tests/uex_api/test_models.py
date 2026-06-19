"""Unit tests for src.uex_api.models — from_api parsing and derived properties."""

from src.uex_api.models import Commodity, CommodityPrice, Terminal, Vehicle


class TestCommodityFromApi:
    def test_parses_id_as_int(self):
        assert Commodity.from_api({"id": "5"}).id == 5

    def test_parses_name(self):
        assert Commodity.from_api({"name": "Gold"}).name == "Gold"

    def test_falls_back_to_unknown_when_name_missing(self):
        assert Commodity.from_api({}).name == "Unknown"

    def test_parses_price_buy_as_float(self):
        assert Commodity.from_api({"price_buy": "15.5"}).price_buy == 15.5

    def test_none_for_missing_numeric_fields(self):
        c = Commodity.from_api({})
        assert c.price_buy is None
        assert c.price_sell is None

    def test_none_for_missing_id(self):
        assert Commodity.from_api({}).id is None

    def test_invalid_id_returns_none(self):
        assert Commodity.from_api({"id": "not-a-number"}).id is None


class TestCommodityPricePlaceType:
    def test_space_station_wins(self):
        p = CommodityPrice.from_api({"space_station_name": "CRU-L1"})
        assert p.place_type == "station"

    def test_outpost(self):
        p = CommodityPrice.from_api({"outpost_name": "Shubin Mining SA-1"})
        assert p.place_type == "outpost"

    def test_city(self):
        p = CommodityPrice.from_api({"city_name": "Lorville"})
        assert p.place_type == "city"

    def test_moon(self):
        p = CommodityPrice.from_api({"moon_name": "Cellin"})
        assert p.place_type == "moon"

    def test_planet(self):
        p = CommodityPrice.from_api({"planet_name": "Hurston"})
        assert p.place_type == "planet"

    def test_other_when_no_location_set(self):
        p = CommodityPrice.from_api({})
        assert p.place_type == "other"

    def test_station_takes_priority_over_planet(self):
        p = CommodityPrice.from_api({"space_station_name": "CRU-L1", "planet_name": "Crusader"})
        assert p.place_type == "station"

    def test_outpost_takes_priority_over_moon(self):
        p = CommodityPrice.from_api({"outpost_name": "Shubin", "moon_name": "Cellin"})
        assert p.place_type == "outpost"


class TestTerminalFromApi:
    def test_defaults_name_to_unknown(self):
        assert Terminal.from_api({}).name == "Unknown"

    def test_parses_name(self):
        assert Terminal.from_api({"name": "Refinery Desk"}).name == "Refinery Desk"

    def test_parses_id_as_int(self):
        assert Terminal.from_api({"id": "42"}).id == 42

    def test_none_for_missing_id(self):
        assert Terminal.from_api({}).id is None

    def test_parses_boolean_flag_true(self):
        assert Terminal.from_api({"has_loading_dock": True}).has_loading_dock is True

    def test_parses_boolean_flag_false(self):
        assert Terminal.from_api({"has_loading_dock": False}).has_loading_dock is False

    def test_parses_star_system_name(self):
        t = Terminal.from_api({"star_system_name": "Stanton"})
        assert t.star_system_name == "Stanton"

    def test_parses_max_container_size_as_int(self):
        t = Terminal.from_api({"max_container_size": "32"})
        assert t.max_container_size == 32


class TestVehicleFromApi:
    def test_defaults_name_to_unknown(self):
        assert Vehicle.from_api({}).name == "Unknown"

    def test_parses_scu_as_float(self):
        assert Vehicle.from_api({"scu": "576"}).scu == 576.0

    def test_parses_crew_as_int(self):
        assert Vehicle.from_api({"crew": "3"}).crew == 3

    def test_none_scu_when_missing(self):
        assert Vehicle.from_api({}).scu is None
