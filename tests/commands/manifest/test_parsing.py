import pytest

from src.commands.manifest import parsing
from src.commands.manifest.ledger import ManifestError


def test_parse_cargo_name_and_scu():
    assert parsing.parse_cargo("Gold 96") == [{"commodity": "Gold", "scu": 96, "est_price": None}]


def test_parse_cargo_with_price_and_multi_word_name():
    text = "Recycled  Material Composite 12 1,800\nQuantanium 3 88000.5"
    assert parsing.parse_cargo(text) == [
        {"commodity": "Recycled Material Composite", "scu": 12, "est_price": 1800.0},
        {"commodity": "Quantanium", "scu": 3, "est_price": 88000.5},
    ]


def test_parse_cargo_skips_blank_lines_and_keeps_spelling():
    assert parsing.parse_cargo("\n  gold 5  \n\n") == [{"commodity": "gold", "scu": 5, "est_price": None}]


def test_parse_cargo_merges_duplicates():
    assert parsing.parse_cargo("Gold 10 100\ngold 5\nGOLD 1 200") == [
        {"commodity": "Gold", "scu": 16, "est_price": 200.0}
    ]


def test_parse_cargo_reports_every_bad_line():
    with pytest.raises(ManifestError) as error:
        parsing.parse_cargo("Gold\nTin 0\nIron 1 2 3\nCopper 2000000\n5 6\nAgricium 2 -1")
    message = str(error.value)
    assert "Line 1:" in message
    assert "Line 2:" in message
    assert "Line 3:" in message
    assert "Line 4:" in message
    assert "Line 5:" in message
    assert "Line 6:" in message


def test_parse_cargo_rejects_decimal_scu():
    with pytest.raises(ManifestError, match="Line 1"):
        parsing.parse_cargo("Gold 1.5")


def test_parse_cargo_requires_a_line():
    with pytest.raises(ManifestError, match="at least one commodity"):
        parsing.parse_cargo("  \n ")


def test_parse_cargo_limits_lines():
    with pytest.raises(ManifestError, match="20"):
        parsing.parse_cargo("\n".join(f"Item{i} 1" for i in range(21)))


def test_parse_costs():
    assert parsing.parse_costs("Fuel 20,000\nCargo purchase 150000") == [
        {"label": "Fuel", "amount": 20000},
        {"label": "Cargo purchase", "amount": 150000},
    ]


def test_parse_costs_empty_is_fine():
    assert parsing.parse_costs("") == []


def test_parse_costs_reports_bad_lines():
    with pytest.raises(ManifestError) as error:
        parsing.parse_costs("Fuel\nRepairs 0\n20000\nTip 1.5")
    message = str(error.value)
    for number in range(1, 5):
        assert f"Line {number}:" in message


def test_format_round_trips():
    cargo = [
        {"commodity": "Gold", "scu": 96, "est_price": 6500.0},
        {"commodity": "Recycled Material Composite", "scu": 12, "est_price": None},
        {"commodity": "Quantanium", "scu": 3, "est_price": 88000.5},
    ]
    costs = [{"label": "Fuel", "amount": 20000}]
    assert parsing.format_cargo(cargo) == "Gold 96 6500\nRecycled Material Composite 12\nQuantanium 3 88000.5"
    assert parsing.parse_cargo(parsing.format_cargo(cargo)) == cargo
    assert parsing.parse_costs(parsing.format_costs(costs)) == costs


def test_parse_cargo_rejects_merged_total_over_limit():
    with pytest.raises(ManifestError, match="Gold adds up to more than"):
        parsing.parse_cargo("Gold 1000000\nGold 1")
