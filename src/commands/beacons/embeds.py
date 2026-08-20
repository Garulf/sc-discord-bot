"""Embed builders for the beacon panel and individual beacons."""

from __future__ import annotations

from typing import Any

import discord

from .categories import CATEGORIES, short_label
from .location import format_breadcrumb, parse_location
from .rules import STATUS_ACTIVE, STATUS_CLOSED

_STATUS_COLORS = {
    "open": discord.Color.green(),
    "active": discord.Color.gold(),
    "closed": discord.Color.dark_grey(),
}


_TITLE_LIMIT = 100


def _place(value: str | None) -> str | None:
    if not value:
        return None
    parts = parse_location(value)
    return parts[-1] if parts else value


def _title_summary(category_key: str, fields: dict[str, Any]) -> str | None:
    place = _place(fields.get("location"))
    destination = _place(fields.get("destination"))
    if category_key == "medic":
        return _join_present(fields.get("tier"), f"@ {place}" if place else None)
    if category_key == "backup":
        threat = fields.get("threat")
        urgency = fields.get("urgency")
        versus = " vs ".join(part for part in (urgency, threat) if part) or None
        return _join_present(versus, f"@ {place}" if place else None)
    if category_key == "cargo":
        route = " to ".join(p for p in (_place(fields.get("route_from")), _place(fields.get("route_to"))) if p)
        scu = fields.get("scu")
        return _join_present(route or None, f"({scu} SCU)" if scu else None)
    if category_key in ("escort", "transport"):
        route = " to ".join(part for part in (place, destination) if part)
        return route or None
    if category_key == "squad":
        size = fields.get("size")
        return _join_present(f"{size} needed" if size else None, f"@ {place}" if place else None)
    if category_key == "contested":
        return _join_present(fields.get("objective"), f"@ {place}" if place else None)
    detail = fields.get("need") or fields.get("target")
    return _join_present(detail, f"@ {place}" if place else None)


def _join_present(*parts: str | None) -> str | None:
    present = [part for part in parts if part]
    return " ".join(present) if present else None


def beacon_title(category_key: str, username: str, fields: dict[str, Any] | None = None) -> str:
    label = f"[{short_label(CATEGORIES[category_key])}]"
    summary = _title_summary(category_key, fields or {})
    title = f"{label} {summary} · {username}" if summary else f"{label} {username}"
    return title[:_TITLE_LIMIT]


def _add_category_fields(embed: discord.Embed, category, fields: dict[str, Any]) -> None:
    for spec in category.fields:
        value = fields.get(spec.key)
        if not value:
            continue
        shown = format_breadcrumb(value) if spec.kind in ("location", "route") else value
        embed.add_field(name=spec.label, value=shown, inline=False)


def build_beacon_embed(beacon: dict[str, Any]) -> discord.Embed:
    category = CATEGORIES[beacon["category"]]
    embed = discord.Embed(
        title=f"{category.emoji} {category.label} beacon",
        color=_STATUS_COLORS[beacon["status"]],
    )
    embed.add_field(name="Requester", value=f"<@{beacon['requester_id']}>", inline=True)
    embed.add_field(name="Status", value=_status_text(beacon), inline=True)
    if beacon["members"]:
        responders = ", ".join(f"<@{member}>" for member in beacon["members"])
        size = beacon["fields"].get("size")
        name = f"Responders ({len(beacon['members'])}/{size})" if size else "Responders"
        embed.add_field(name=name, value=responders, inline=False)
    _add_category_fields(embed, category, beacon["fields"])
    embed.add_field(name="Opened", value=f"<t:{int(beacon['opened_at'])}:R>", inline=True)
    return embed


def _status_text(beacon: dict[str, Any]) -> str:
    if beacon["status"] == STATUS_ACTIVE:
        return "Active"
    if beacon["status"] == STATUS_CLOSED:
        closed_at = int(beacon["closed_at"]) if beacon["closed_at"] else None
        when = f" <t:{closed_at}:R>" if closed_at else ""
        return f"Closed by <@{beacon['closed_by_id']}>{when}"
    return "Open"


def build_scheduled_embed(
    scheduled: dict[str, Any], *, cancelled_by_id: int | None = None, opened_thread_id: int | None = None
) -> discord.Embed:
    category = CATEGORIES[scheduled["category"]]
    embed = discord.Embed(
        title=f"{category.emoji} {category.label} beacon (scheduled)",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Requester", value=f"<@{scheduled['requester_id']}>", inline=True)
    embed.add_field(
        name="Status", value=_scheduled_status_text(scheduled, cancelled_by_id, opened_thread_id), inline=True
    )
    if scheduled["rsvp"]:
        rsvp = ", ".join(f"<@{user_id}>" for user_id in scheduled["rsvp"])
        embed.add_field(name=f"RSVP ({len(scheduled['rsvp'])})", value=rsvp, inline=False)
    _add_category_fields(embed, category, scheduled["fields"])
    if opened_thread_id is not None:
        embed.add_field(name="Thread", value=f"<#{opened_thread_id}>", inline=False)
    return embed


def _scheduled_status_text(scheduled: dict[str, Any], cancelled_by_id: int | None, opened_thread_id: int | None) -> str:
    open_at = int(scheduled["open_at"])
    if opened_thread_id is not None:
        return f"Opened <t:{open_at}:R>"
    if cancelled_by_id is not None:
        return f"Cancelled by <@{cancelled_by_id}>"
    return f"Opens <t:{open_at}:R> (<t:{open_at}:f>)"


def build_panel_content(mention) -> str:
    lines = [f"{c.emoji} {mention(c.key)}: {c.description}" for c in CATEGORIES.values()]
    return "**Service Beacons**\nNeed a hand in the verse? Click a command below to open a beacon.\n\n" + "\n".join(
        lines
    )
