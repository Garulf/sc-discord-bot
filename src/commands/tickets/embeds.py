"""Embed builders for the ticket panel and individual tickets."""

from __future__ import annotations

from typing import Any

import discord

from .categories import CATEGORIES
from .location import format_breadcrumb
from .rules import STATUS_CLAIMED, STATUS_CLOSED

_LOCATION_KEYS = {"location", "route_from", "route_to"}

_STATUS_COLORS = {
    "open": discord.Color.green(),
    "claimed": discord.Color.gold(),
    "closed": discord.Color.dark_grey(),
}


def ticket_title(category_key: str, username: str) -> str:
    return f"[{CATEGORIES[category_key].label.split(' (')[0]}] {username}"


def build_ticket_embed(ticket: dict[str, Any]) -> discord.Embed:
    category = CATEGORIES[ticket["category"]]
    embed = discord.Embed(
        title=f"{category.emoji} {category.label} ticket",
        color=_STATUS_COLORS[ticket["status"]],
    )
    embed.add_field(name="Requester", value=f"<@{ticket['requester_id']}>", inline=True)
    embed.add_field(name="Status", value=_status_text(ticket), inline=True)
    for spec in category.fields:
        value = ticket["fields"].get(spec.key)
        if not value:
            continue
        shown = format_breadcrumb(value) if spec.key in _LOCATION_KEYS else value
        embed.add_field(name=spec.label, value=shown, inline=False)
    embed.add_field(name="Opened", value=f"<t:{int(ticket['opened_at'])}:R>", inline=True)
    return embed


def _status_text(ticket: dict[str, Any]) -> str:
    if ticket["status"] == STATUS_CLAIMED:
        return f"Claimed by <@{ticket['claimer_id']}>"
    if ticket["status"] == STATUS_CLOSED:
        closed_at = int(ticket["closed_at"]) if ticket["closed_at"] else None
        when = f" <t:{closed_at}:R>" if closed_at else ""
        return f"Closed by <@{ticket['closed_by_id']}>{when}"
    return "Open"


def build_panel_embed() -> discord.Embed:
    lines = [f"{c.emoji} **{c.label}**" for c in CATEGORIES.values()]
    return discord.Embed(
        title="Open a ticket",
        description=(
            "Need a hand in the verse? Pick a category below to get the command, "
            "or run `/ticket <category>` directly.\n\n" + "\n".join(lines)
        ),
        color=discord.Color.blurple(),
    )
