"""Embed builders for the beacon panel and individual beacons."""

from __future__ import annotations

from typing import Any

import discord

from .categories import CATEGORIES, short_label
from .location import format_breadcrumb
from .rules import STATUS_CLAIMED, STATUS_CLOSED

_STATUS_COLORS = {
    "open": discord.Color.green(),
    "claimed": discord.Color.gold(),
    "closed": discord.Color.dark_grey(),
}


def beacon_title(category_key: str, username: str) -> str:
    return f"[{short_label(CATEGORIES[category_key])}] {username}"


def build_beacon_embed(beacon: dict[str, Any]) -> discord.Embed:
    category = CATEGORIES[beacon["category"]]
    embed = discord.Embed(
        title=f"{category.emoji} {category.label} beacon",
        color=_STATUS_COLORS[beacon["status"]],
    )
    embed.add_field(name="Requester", value=f"<@{beacon['requester_id']}>", inline=True)
    embed.add_field(name="Status", value=_status_text(beacon), inline=True)
    for spec in category.fields:
        value = beacon["fields"].get(spec.key)
        if not value:
            continue
        shown = format_breadcrumb(value) if spec.kind in ("location", "route") else value
        embed.add_field(name=spec.label, value=shown, inline=False)
    embed.add_field(name="Opened", value=f"<t:{int(beacon['opened_at'])}:R>", inline=True)
    return embed


def _status_text(beacon: dict[str, Any]) -> str:
    if beacon["status"] == STATUS_CLAIMED:
        return f"Claimed by <@{beacon['claimer_id']}>"
    if beacon["status"] == STATUS_CLOSED:
        closed_at = int(beacon["closed_at"]) if beacon["closed_at"] else None
        when = f" <t:{closed_at}:R>" if closed_at else ""
        return f"Closed by <@{beacon['closed_by_id']}>{when}"
    return "Open"


def build_panel_embed() -> discord.Embed:
    lines = [f"{c.emoji} **{c.label}**: {c.description}" for c in CATEGORIES.values()]
    return discord.Embed(
        title="Open a beacon",
        description=(
            "Need a hand in the verse? Pick a category below to get the command, "
            "or run `/beacon <category>` directly.\n\n" + "\n".join(lines)
        ),
        color=discord.Color.blurple(),
    )
