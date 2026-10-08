"""Resolve typed commodity names against UEX and fill in estimated sell prices."""

from __future__ import annotations

import logging
from typing import Any

from .ledger import ManifestError, Record
from .parsing import merge_cargo

logger = logging.getLogger(__name__)


async def _canonical_names(bot: Any, cargo: list[Record]) -> dict[str, Any] | None:
    found = {}
    try:
        for line in cargo:
            found[line["commodity"]] = await bot.commodities_api.find(line["commodity"])
    except Exception:  # noqa: BLE001 - an unreachable catalogue must not block creating a manifest
        logger.warning("Could not look up commodities on UEX; accepting names as typed")
        return None
    return found


def _exact(commodity: Any, typed: str) -> bool:
    needle = typed.strip().lower()
    return commodity is not None and needle in (commodity.name.lower(), (commodity.code or "").lower())


async def _best_sell(bot: Any, commodity_id: int) -> float | None:
    try:
        best = await bot.commodity_prices_api.best_sell(commodity_id)
    except Exception:  # noqa: BLE001 - estimates are decoration and must never block a manifest change
        logger.warning("Could not estimate a price for commodity %s", commodity_id)
        return None
    return best.price_sell if best is not None else None


async def resolve_cargo(bot: Any, cargo: list[Record]) -> list[Record]:
    found = await _canonical_names(bot, cargo)
    if found is None:
        return cargo
    unknown = [line["commodity"] for line in cargo if not _exact(found[line["commodity"]], line["commodity"])]
    if unknown:
        raise ManifestError(f"Unknown commodities: {', '.join(unknown)}. Check the spelling against UEX.")
    resolved = merge_cargo([{**line, "commodity": found[line["commodity"]].name} for line in cargo])
    ids = {found[line["commodity"]].name: found[line["commodity"]].id for line in cargo}
    for line in resolved:
        if line["est_price"] is None and ids[line["commodity"]] is not None:
            line["est_price"] = await _best_sell(bot, ids[line["commodity"]])
    return resolved
