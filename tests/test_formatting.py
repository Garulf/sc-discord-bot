"""Unit tests for src.commands.formatting — format_number and format_shop."""

from src.commands.formatting import format_number, format_shop
from src.starcitizenwiki_api.weapons import PurchaseLocation


class TestFormatNumber:
    def test_none_returns_none(self):
        assert format_number(None) is None

    def test_integer_value_no_decimal(self):
        assert format_number(1000.0) == "1,000"

    def test_float_keeps_two_decimals(self):
        assert format_number(1234.56) == "1,234.56"

    def test_with_suffix(self):
        assert format_number(500.0, " aUEC") == "500 aUEC"

    def test_zero(self):
        assert format_number(0.0) == "0"

    def test_small_float(self):
        assert format_number(1.5) == "1.5"

    def test_large_number_has_thousands_separator(self):
        assert format_number(1_000_000.0) == "1,000,000"


class TestFormatShop:
    def test_all_fields_present(self):
        shop = PurchaseLocation(
            price_buy=1500.0,
            terminal_name="Refinery Desk",
            location_name="Lorville",
            star_system="Stanton",
        )
        result = format_shop(shop)
        assert "1,500 aUEC" in result
        assert "Refinery Desk" in result
        assert "Lorville" in result
        assert "Stanton" in result

    def test_no_price_shows_placeholder(self):
        shop = PurchaseLocation(
            price_buy=None,
            terminal_name="Unknown Vendor",
            location_name=None,
            star_system=None,
        )
        assert "price n/a" in format_shop(shop)

    def test_no_location_omits_parentheses(self):
        shop = PurchaseLocation(
            price_buy=100.0,
            terminal_name="Kiosk",
            location_name=None,
            star_system=None,
        )
        result = format_shop(shop)
        assert "100 aUEC" in result
        assert "Kiosk" in result
        assert "(" not in result

    def test_location_without_system(self):
        shop = PurchaseLocation(
            price_buy=200.0,
            terminal_name="Terminal",
            location_name="New Babbage",
            star_system=None,
        )
        result = format_shop(shop)
        assert "New Babbage" in result
        assert "(" in result
