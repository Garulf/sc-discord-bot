"""Executive Hangar tracking: status, manual state entry, and live
auto-updating subscriptions. State persists via the bot's StateStore so a
restart recovers the current cycle and any subscribed messages.

Subcommand, state, and refresh logic live in individual files; this module
contains only the Cog class (command registration and task-loop wiring)."""

from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

from src.commands.checks import admin_or_sc_bot, handle_check_failure
from src.exec_hangars import HangarSchedule

from .set import handle as _handle_set
from .shared import load_state, refresh_subscriptions
from .status import handle as _handle_status
from .subscribe import handle as _handle_subscribe
from .unsubscribe import handle as _handle_unsubscribe

UPDATE_INTERVAL_SECONDS = 30


class HangarCog(commands.Cog):
    """Commands and background loop for the Executive Hangar."""

    hangar = app_commands.Group(name="hangar", description="Executive Hangar tracking")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.schedule: HangarSchedule | None = None
        self.set_at: datetime | None = None
        self.subscriptions: list[dict] = []

    async def cog_load(self) -> None:
        await load_state(self)
        self.update_loop.start()

    async def cog_unload(self) -> None:
        self.update_loop.cancel()

    @tasks.loop(seconds=UPDATE_INTERVAL_SECONDS)
    async def update_loop(self) -> None:
        await refresh_subscriptions(self)

    @update_loop.before_loop
    async def before_update_loop(self) -> None:
        await self.bot.wait_until_ready()

    @update_loop.error
    async def update_loop_error(self, error: Exception) -> None:
        logger.exception("Hangar update loop stopped unexpectedly: %s", error)

    @hangar.command(name="status", description="Show the current Executive Hangar status")
    async def status(self, interaction: discord.Interaction):
        await _handle_status(self, interaction)

    @hangar.command(name="set", description="Set the current Executive Hangar state")
    @app_commands.describe(
        phase="The phase the hangar is currently in",
        lights="Charging: green lights lit. Open: lights already expired. (0-5)",
    )
    @app_commands.choices(
        phase=[
            app_commands.Choice(name="Charging (closed, lights filling green)", value="charging"),
            app_commands.Choice(name="Open (active, lights expiring)", value="active"),
            app_commands.Choice(name="Resetting (orange / blinking)", value="reset"),
        ]
    )
    async def set(
        self,
        interaction: discord.Interaction,
        phase: app_commands.Choice[str],
        lights: app_commands.Range[int, 0, 5] = 0,
    ):
        await _handle_set(self, interaction, phase, lights)

    @hangar.command(
        name="subscribe",
        description="Post a live Executive Hangar status in this channel that auto-updates",
    )
    @app_commands.check(admin_or_sc_bot)
    async def subscribe(self, interaction: discord.Interaction):
        await _handle_subscribe(self, interaction)

    @hangar.command(
        name="unsubscribe",
        description="Stop and remove live Executive Hangar status messages in this channel",
    )
    @app_commands.check(admin_or_sc_bot)
    async def unsubscribe(self, interaction: discord.Interaction):
        await _handle_unsubscribe(self, interaction)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handle_check_failure(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HangarCog(bot))
