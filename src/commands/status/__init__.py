"""The /status command group: show RSI server status and subscribe channels to
updates. A background task polls the RSI status feed and posts new or updated
incidents to subscribed channels."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot
from src.rsi_status import STATUS_FEED_URL, StatusOverview, fetch_status_entries, fetch_status_overview

from .constants import POLL_MINUTES, SEEN_KEY, SUBSCRIPTIONS_KEY, SYSTEMS_KEY
from .embeds import build_overview_embed, build_status_embed, normalize_link
from .show import handle as _handle_show
from .subscribe import handle as _handle_subscribe
from .unsubscribe import handle as _handle_unsubscribe


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
        await _handle_show(self, interaction)

    @status.command(name="subscribe", description="Post RSI server status updates in this channel")
    @app_commands.check(admin_or_sc_bot)
    async def subscribe(self, interaction: discord.Interaction):
        await _handle_subscribe(self, interaction)

    @status.command(
        name="unsubscribe",
        description="Stop posting RSI server status updates in this channel",
    )
    @app_commands.check(admin_or_sc_bot)
    async def unsubscribe(self, interaction: discord.Interaction):
        await _handle_unsubscribe(self, interaction)

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
            (name, previous.get(name), status) for name, status in current.items() if previous.get(name) != status
        ]
        if changes:
            await self._broadcast(subscriptions, build_overview_embed(overview, changes=changes))
        await self.bot.state.set(SYSTEMS_KEY, current)

    async def _latest_incident(self, overview: StatusOverview) -> tuple[str, str, str | None] | None:
        """The most recent unresolved incident as ``(title, message, link)``, or None."""
        unresolved = {normalize_link(issue.link) for system in overview.systems for issue in system.unresolved}
        if not unresolved:
            return None
        try:
            entries = await fetch_status_entries(STATUS_FEED_URL)
        except Exception as e:  # noqa: BLE001 - the message is best-effort
            print(f"RSI status message lookup failed: {e}")
            return None
        for entry in entries:
            if entry.summary and normalize_link(entry.link or entry.guid) in unresolved:
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
