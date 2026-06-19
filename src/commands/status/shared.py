"""Shared code for the /status command group.

Contains constants, embed builders, text helpers, and background polling logic
used by the StatusCog and its subcommands.
"""

from __future__ import annotations

import logging

import discord

from src.rsi_status import (
    STATUS_FEED_URL,
    STATUS_PAGE_URL,
    StatusEntry,
    StatusOverview,
    fetch_status_entries,
    fetch_status_overview,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POLL_MINUTES = 5
STATUS_COLOR = 0xE03B3B
MAX_SUMMARY = 600
MAX_ISSUE_MESSAGE = 400

SUBSCRIPTIONS_KEY = "status_subscriptions"
SEEN_KEY = "status_seen"
SYSTEMS_KEY = "status_systems"

STATUS_LABEL = {
    "operational": "Operational",
    "degraded": "Degraded",
    "partial": "Partial Outage",
    "major": "Major Outage",
    "maintenance": "Maintenance",
}
OVERVIEW_COLOR = {
    "operational": 0x51AE7A,
    "degraded": 0x969AE8,
    "partial": 0xE8944A,
    "major": 0xFF6666,
    "maintenance": 0xAAB5BB,
}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


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


def normalize_link(url: str | None) -> str:
    cleaned = (url or "").strip()
    if cleaned.endswith("index.html"):
        cleaned = cleaned[: -len("index.html")]
    return cleaned.rstrip("/")

# ---------------------------------------------------------------------------
# Embed builders
# ---------------------------------------------------------------------------


def build_overview_embed(
    overview: StatusOverview,
    *,
    changes: list[tuple[str, str, str]] | None = None,
    incident: tuple[str, str, str | None] | None = None,
) -> discord.Embed:
    description_parts = []
    if changes:
        description_parts.append(
            "**Status changed**\n"
            + "\n".join(f"{name}: {status_text(old or 'unknown')} → {status_text(new)}" for name, old, new in changes)
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
    embed = discord.Embed(title=entry.title[:256], url=entry.link or None, color=STATUS_COLOR)
    if entry.summary:
        embed.description = entry.summary[:MAX_SUMMARY] + ("…" if len(entry.summary) > MAX_SUMMARY else "")
    footer = "RSI Status"
    if entry.published:
        footer += f" · {entry.published}"
    embed.set_footer(text=footer)
    return embed

# ---------------------------------------------------------------------------
# Background polling
# ---------------------------------------------------------------------------


async def poll(cog) -> None:
    """One poll pass: broadcast new incidents and component status changes."""
    subscriptions = await cog.bot.state.get(SUBSCRIPTIONS_KEY, [])
    if not subscriptions:
        return
    await _poll_incidents(cog, subscriptions)
    await _poll_systems(cog, subscriptions)


async def _poll_incidents(cog, subscriptions: list[int]) -> None:
    try:
        entries = await fetch_status_entries(STATUS_FEED_URL)
    except Exception:  # noqa: BLE001 - log and keep the loop alive
        logger.exception("RSI status feed poll failed")
        return
    if not entries:
        return

    current = {entry.guid: (entry.published or "") for entry in entries}
    seen = await cog.bot.state.get(SEEN_KEY, {})
    if not seen:
        await cog.bot.state.set(SEEN_KEY, current)
        return

    updated = [entry for entry in entries if seen.get(entry.guid) != current[entry.guid]]
    for entry in reversed(updated):
        await _broadcast(cog, subscriptions, build_status_embed(entry))

    await cog.bot.state.set(SEEN_KEY, current)


async def _poll_systems(cog, subscriptions: list[int]) -> None:
    try:
        overview = await fetch_status_overview()
    except Exception:  # noqa: BLE001 - log and keep the loop alive
        logger.exception("RSI status overview poll failed")
        return

    current = {system.name: system.status for system in overview.systems}
    if not current:
        return
    previous = await cog.bot.state.get(SYSTEMS_KEY, {})
    if not previous:
        await cog.bot.state.set(SYSTEMS_KEY, current)
        return

    changes = [
        (name, previous.get(name), status) for name, status in current.items() if previous.get(name) != status
    ]
    if changes:
        await _broadcast(cog, subscriptions, build_overview_embed(overview, changes=changes))
    await cog.bot.state.set(SYSTEMS_KEY, current)


async def latest_incident(cog, overview: StatusOverview) -> tuple[str, str, str | None] | None:
    """The most recent unresolved incident as ``(title, message, link)``, or None."""
    unresolved = {normalize_link(issue.link) for system in overview.systems for issue in system.unresolved}
    if not unresolved:
        return None
    try:
        entries = await fetch_status_entries(STATUS_FEED_URL)
    except Exception:  # noqa: BLE001 - the message is best-effort
        logger.exception("RSI status message lookup failed")
        return None
    for entry in entries:
        if entry.summary and normalize_link(entry.link or entry.guid) in unresolved:
            return (entry.title, entry.summary, entry.link)
    return None


async def _broadcast(cog, subscriptions: list[int], embed: discord.Embed) -> None:
    for channel_id in subscriptions:
        channel = cog.bot.get_channel(channel_id)
        if channel is None:
            continue
        try:
            await channel.send(embed=embed)
        except discord.DiscordException:
            pass
