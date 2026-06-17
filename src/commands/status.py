"""The ``/status`` subcommand group: show RSI server status and opt channels
in or out of RSI server status updates. A background task polls the RSI status
feed and posts new or updated incidents to subscribed channels. Channel
subscriptions and the last-seen incidents persist in ``bot.state`` (SQLite)."""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot
from src.rsi_status import (
    STATUS_FEED_URL,
    STATUS_PAGE_URL,
    StatusEntry,
    StatusOverview,
    fetch_status_entries,
    fetch_status_overview,
)

POLL_MINUTES = 5
STATUS_COLOR = 0xE03B3B
MAX_SUMMARY = 600
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


MAX_ISSUE_MESSAGE = 400

def _status_text(status: str) -> str:
    return STATUS_LABEL.get(status, status.replace("_", " ").title())


def _truncate(text: str, limit: int) -> str:
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


def _normalize_link(url: Optional[str]) -> str:
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
    framed as a status-change alert highlighting what moved. ``incident`` is the
    latest relevant ``(title, message)``, shown once at the bottom.
    """
    description_parts = []
    if changes:
        description_parts.append(
            "**Status changed**\n"
            + "\n".join(
                f"{name}: {_status_text(old or 'unknown')} → {_status_text(new)}"
                for name, old, new in changes
            )
        )
    description_parts.append(f"**Overall:** {_status_text(overview.summary_status)}")

    embed = discord.Embed(
        title="RSI Status Alert" if changes else "RSI Server Status",
        url=STATUS_PAGE_URL,
        description="\n\n".join(description_parts),
        color=OVERVIEW_COLOR.get(overview.summary_status, 0x969AE8),
    )
    for system in overview.systems:
        embed.add_field(name=system.name, value=_status_text(system.status), inline=True)

    if incident is not None:
        title, message, link = incident
        body = _truncate(message, MAX_ISSUE_MESSAGE)
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


class StatusCog(commands.Cog):
    """RSI server status subscriptions and the background feed poller."""

    status = app_commands.Group(name="status", description="RSI server status")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.poll_status.start()

    def cog_unload(self) -> None:
        self.poll_status.cancel()

    @status.command(name="show", description="Show RSI server status (Platform, PU, Arena Commander)")
    async def show(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            overview = await fetch_status_overview()
        except Exception as e:  # noqa: BLE001 - surface a friendly message
            await interaction.followup.send(
                f"Couldn't reach the RSI status page right now: {e}", ephemeral=True
            )
            return
        incident = await self._latest_incident(overview)
        await interaction.followup.send(embed=build_overview_embed(overview, incident=incident))

    @status.command(name="subscribe", description="Post RSI server status updates in this channel")
    @app_commands.check(admin_or_sc_bot)
    async def subscribe(self, interaction: discord.Interaction):
        if interaction.channel_id is None:
            await interaction.response.send_message(
                "This command can only be used in a channel.", ephemeral=True
            )
            return
        subscriptions = await self.bot.state.get(SUBSCRIPTIONS_KEY, [])
        if interaction.channel_id in subscriptions:
            await interaction.response.send_message(
                "This channel is already subscribed to RSI status updates.", ephemeral=True
            )
            return
        subscriptions.append(interaction.channel_id)
        await self.bot.state.set(SUBSCRIPTIONS_KEY, subscriptions)
        await interaction.response.send_message(
            "Subscribed — new RSI status updates will be posted here.", ephemeral=True
        )

    @status.command(
        name="unsubscribe",
        description="Stop posting RSI server status updates in this channel",
    )
    @app_commands.check(admin_or_sc_bot)
    async def unsubscribe(self, interaction: discord.Interaction):
        subscriptions = await self.bot.state.get(SUBSCRIPTIONS_KEY, [])
        if interaction.channel_id not in subscriptions:
            await interaction.response.send_message(
                "This channel isn't subscribed to RSI status updates.", ephemeral=True
            )
            return
        subscriptions = [c for c in subscriptions if c != interaction.channel_id]
        await self.bot.state.set(SUBSCRIPTIONS_KEY, subscriptions)
        await interaction.response.send_message(
            "Unsubscribed from RSI status updates.", ephemeral=True
        )

    @tasks.loop(minutes=POLL_MINUTES)
    async def poll_status(self) -> None:
        subscriptions = await self.bot.state.get(SUBSCRIPTIONS_KEY, [])
        if not subscriptions:
            return
        await self._poll_incidents(subscriptions)
        await self._poll_systems(subscriptions)

    async def _poll_incidents(self, subscriptions: list[int]) -> None:
        try:
            entries = await fetch_status_entries(STATUS_FEED_URL)
        except Exception as e:  # noqa: BLE001 - log and keep the loop alive
            print(f"RSI status feed poll failed: {e}")
            return
        if not entries:
            return

        current = {entry.guid: (entry.published or "") for entry in entries}
        seen = await self.bot.state.get(SEEN_KEY, {})
        # First run: remember the current feed without replaying its history.
        if not seen:
            await self.bot.state.set(SEEN_KEY, current)
            return

        updated = [entry for entry in entries if seen.get(entry.guid) != current[entry.guid]]
        for entry in reversed(updated):
            await self._broadcast(subscriptions, build_status_embed(entry))

        await self.bot.state.set(SEEN_KEY, current)

    async def _poll_systems(self, subscriptions: list[int]) -> None:
        try:
            overview = await fetch_status_overview()
        except Exception as e:  # noqa: BLE001 - log and keep the loop alive
            print(f"RSI status overview poll failed: {e}")
            return

        current = {system.name: system.status for system in overview.systems}
        if not current:
            return
        previous = await self.bot.state.get(SYSTEMS_KEY, {})
        # First run: remember component statuses without alerting.
        if not previous:
            await self.bot.state.set(SYSTEMS_KEY, current)
            return

        changes = [
            (name, previous.get(name), status)
            for name, status in current.items()
            if previous.get(name) != status
        ]
        if changes:
            incident = await self._latest_incident(overview)
            embed = build_overview_embed(overview, changes=changes, incident=incident)
            await self._broadcast(subscriptions, embed)
        await self.bot.state.set(SYSTEMS_KEY, current)

    async def _latest_incident(self, overview: StatusOverview) -> Optional[tuple[str, str, Optional[str]]]:
        """The most recent unresolved incident as ``(title, message, link)``, or None.

        Only fetches the feed when something is unresolved; the feed is ordered
        newest-first, so the first matching entry is the latest relevant message.
        """
        unresolved = {
            _normalize_link(issue.link)
            for system in overview.systems
            for issue in system.unresolved
        }
        if not unresolved:
            return None
        try:
            entries = await fetch_status_entries(STATUS_FEED_URL)
        except Exception as e:  # noqa: BLE001 - the message is best-effort
            print(f"RSI status message lookup failed: {e}")
            return None
        for entry in entries:
            if entry.summary and _normalize_link(entry.link or entry.guid) in unresolved:
                return (entry.title, entry.summary, entry.link)
        return None

    async def _broadcast(self, subscriptions: list[int], embed: discord.Embed) -> None:
        for channel_id in subscriptions:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                continue
            try:
                await channel.send(embed=embed)
            except discord.DiscordException:
                pass

    @poll_status.before_loop
    async def before_poll(self) -> None:
        await self.bot.wait_until_ready()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            msg = str(error) or "You don't have permission to use this command."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatusCog(bot))
