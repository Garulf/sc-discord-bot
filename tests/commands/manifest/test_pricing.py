from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.manifest import pricing
from src.commands.manifest.ledger import ManifestError

_CATALOGUE = {
    "gold": SimpleNamespace(id=1, name="Gold", code="GOLD"),
    "quan": SimpleNamespace(id=2, name="Quantanium", code="QUAN"),
    "quantanium": SimpleNamespace(id=2, name="Quantanium", code="QUAN"),
    "gol": SimpleNamespace(id=1, name="Gold", code="GOLD"),
}


def _bot(prices=None, find_error=None, price_error=None):
    bot = MagicMock()

    async def find(name):
        if find_error:
            raise find_error
        return _CATALOGUE.get(name.strip().lower())

    async def best_sell(commodity_id):
        if price_error:
            raise price_error
        price = (prices or {}).get(commodity_id)
        return SimpleNamespace(price_sell=price) if price is not None else None

    bot.commodities_api.find = AsyncMock(side_effect=find)
    bot.commodity_prices_api.best_sell = AsyncMock(side_effect=best_sell)
    return bot


def _line(name, scu=1, price=None):
    return {"commodity": name, "scu": scu, "est_price": price}


async def test_resolves_canonical_names_and_fills_prices():
    bot = _bot(prices={1: 6500.0})
    assert await pricing.resolve_cargo(bot, [_line("gold", 5)]) == [_line("Gold", 5, 6500.0)]


async def test_matches_by_code_and_merges_after_resolving():
    bot = _bot(prices={2: 88000.0})
    resolved = await pricing.resolve_cargo(bot, [_line("QUAN", 2), _line("Quantanium", 3)])
    assert resolved == [_line("Quantanium", 5, 88000.0)]


async def test_keeps_explicit_price():
    bot = _bot(prices={1: 6500.0})
    assert await pricing.resolve_cargo(bot, [_line("Gold", 1, 7000.0)]) == [_line("Gold", 1, 7000.0)]
    bot.commodity_prices_api.best_sell.assert_not_awaited()


async def test_rejects_unknown_and_partial_names():
    bot = _bot()
    with pytest.raises(ManifestError, match="Unknown commodities: gol, Unobtainium"):
        await pricing.resolve_cargo(bot, [_line("gol"), _line("Gold"), _line("Unobtainium")])


async def test_accepts_names_as_typed_when_uex_is_down():
    bot = _bot(find_error=RuntimeError("down"))
    assert await pricing.resolve_cargo(bot, [_line("Whatever", 2)]) == [_line("Whatever", 2)]


async def test_price_lookup_failure_leaves_estimate_empty():
    bot = _bot(price_error=RuntimeError("down"))
    assert await pricing.resolve_cargo(bot, [_line("Gold")]) == [_line("Gold")]
