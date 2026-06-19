"""Shared formatting helpers for Discord embed builders across all commands."""
from __future__ import annotations

from typing import Optional

import discord

from src.starcitizenwiki_api.weapons import PurchaseLocation

MAX_SHOPS_SHOWN = 8


def format_number(value: Optional[float], suffix: str = "") -> Optional[str]:
    """Format a float for display, returning None when the value is absent."""
    if value is None:
        return None
    rounded = round(value, 2)
    if rounded == int(rounded):
        rounded = int(rounded)
    return f"{rounded:,}{suffix}"


def format_shop(shop: PurchaseLocation) -> str:
    """Format a purchase location as 'price — terminal (location, system)'."""
    price = format_number(shop.price_buy, " aUEC") if shop.price_buy else "price n/a"
    place = " · ".join(part for part in (shop.location_name, shop.star_system) if part)
    terminal = shop.terminal_name or "Unknown terminal"
    suffix = f" ({place})" if place else ""
    return f"**{price}** — {terminal}{suffix}"


def add_shops_field(
    embed: discord.Embed,
    purchase_locations: list[PurchaseLocation],
    *,
    max_shown: int = MAX_SHOPS_SHOWN,
    fallback_text: Optional[str] = None,
) -> None:
    """Add a 'Where to Buy' embed field, cheapest first.

    When ``fallback_text`` is provided it is shown as the field value whenever
    there are no priced locations; otherwise the field is omitted entirely.
    """
    shops = [s for s in purchase_locations if s.price_buy is not None]
    if not shops:
        if fallback_text is not None:
            embed.add_field(name="Where to Buy", value=fallback_text, inline=False)
        return
    shops.sort(key=lambda s: s.price_buy or float("inf"))
    lines = [format_shop(s) for s in shops[:max_shown]]
    remaining = len(shops) - max_shown
    if remaining > 0:
        lines.append(f"…and {remaining} more location(s)")
    embed.add_field(name="Where to Buy", value="\n".join(lines), inline=False)
