"""Embed builders and text helpers for /status subcommands."""
from __future__ import annotations

from typing import Optional

import discord

from src.rsi_status import StatusEntry, StatusOverview, STATUS_PAGE_URL
from .constants import MAX_ISSUE_MESSAGE, MAX_SUMMARY, OVERVIEW_COLOR, STATUS_COLOR, STATUS_LABEL


def status_text(status: str) -> str:
    return STATUS_LABEL.get(status, status.replace("_", " ").title())


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "! ", "? "):
        pos = cut.rfind(sep)
        if pos > limit // 2:
            return cut[: pos + 1] + " …"
    pos = cut.rfind(" ")
    if pos > limit // 2:
        return cut[:pos] + " …"
    return cut + "…"


def normalize_link(url: Optional[str]) -> str:
    """Reduce an incident URL to a stable key (feed guid and JSON permalink
    differ only by a trailing ``index.html`` / slash)."""
    cleaned = (url or "").strip()
    if cleaned.endswith("index.html"):
        cleaned = cleaned[: -len("index.html")]
    return cleaned.rstrip("/")


def build_overview_embed(
    overview: StatusOverview,
    *,
    changes: Optional[list[tuple[str, str, str]]] = None,
    incident: Optional[tuple[str, str, Optional[str]]] = None,
) -> discord.Embed:
    """Render the RSI component status overview as a Discord embed.

    When ``changes`` (``(component, old, new)`` tuples) is given, the embed is
    framed as a status-change alert. ``incident`` is the latest relevant
    ``(title, message, link)``, shown once at the bottom.
    """
    description_parts = []
    if changes:
        description_parts.append(
            "**Status changed**\n"
            + "\n".join(
                f"{name}: {status_text(old or 'unknown')} → {status_text(new)}"
                for name, old, new in changes
            )
        )
    description_parts.append(f"**Overall:** {status_text(overview.summary_status)}")

    embed = discord.Embed(
        title="RSI Status Alert" if changes else "RSI Server Status",
        url=STATUS_PAGE_URL,
        description="\n\n".join(description_parts),
        color=OVERVIEW_COLOR.get(overview.summary_status, 0x969AE8),
    )
    for system in overview.systems:
        embed.add_field(name=system.name, value=status_text(system.status), inline=True)

    if incident is not None:
        title, message, link = incident
        body = truncate(message, MAX_ISSUE_MESSAGE)
        if link:
            body += f"\n[Read more]({link})"
        embed.add_field(name=title[:256], value=body, inline=False)

    embed.set_footer(text="status.robertsspaceindustries.com")
    return embed


def build_status_embed(entry: StatusEntry) -> discord.Embed:
    """Render an RSI status incident as a Discord embed."""
    embed = discord.Embed(title=entry.title[:256], url=entry.link or None, color=STATUS_COLOR)
    if entry.summary:
        embed.description = entry.summary[:MAX_SUMMARY] + (
            "…" if len(entry.summary) > MAX_SUMMARY else ""
        )
    footer = "RSI Status"
    if entry.published:
        footer += f" · {entry.published}"
    embed.set_footer(text=footer)
    return embed
