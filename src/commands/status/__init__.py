"""The /status command group: show RSI server status and subscribe channels to
updates. A background task polls the RSI status feed and posts new or updated
incidents to subscribed channels.

Subcommand and polling logic live in individual files; this module contains
only the Cog class (command registration and the task-loop wiring)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot, handle_check_failure

from .shared import POLL_MINUTES, poll
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
        await poll(self)

    @poll_status.before_loop
    async def before_poll(self) -> None:
        await self.bot.wait_until_ready()

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handle_check_failure(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatusCog(bot))
