"""Executive Hangar tracking: status, manual state entry, and live
auto-updating subscriptions. State persists via the bot's StateStore so a
restart recovers the current cycle and any subscribed messages."""

from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot
from src.exec_hangars import HangarSchedule

from .embed import build_embed
from .set import handle as _handle_set
from .status import handle as _handle_status
from .subscribe import handle as _handle_subscribe
from .unsubscribe import handle as _handle_unsubscribe

UPDATE_INTERVAL_SECONDS = 30
_STATE_KEY = "hangar"


class HangarCog(commands.Cog):
    """Commands and background loop for the Executive Hangar."""

    hangar = app_commands.Group(name="hangar", description="Executive Hangar tracking")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.schedule: HangarSchedule | None = None
        self.set_at: datetime | None = None
        self.subscriptions: list[dict] = []

    async def cog_load(self) -> None:
        await self.load_state()
        self.update_loop.start()

    async def cog_unload(self) -> None:
        self.update_loop.cancel()

    async def load_state(self) -> None:
        data = await self.bot.state.get(_STATE_KEY)
        if data is None:
            return
        cycle_start = data.get("cycle_start")
        if cycle_start:
            self.schedule = HangarSchedule(datetime.fromisoformat(cycle_start))
        set_at = data.get("set_at")
        if set_at:
            self.set_at = datetime.fromisoformat(set_at)
        self.subscriptions = data.get("subscriptions", [])

    async def save_state(self) -> None:
        data = {
            "cycle_start": self.schedule.cycle_start.isoformat() if self.schedule else None,
            "set_at": self.set_at.isoformat() if self.set_at else None,
            "subscriptions": self.subscriptions,
        }
        await self.bot.state.set(_STATE_KEY, data)

    async def refresh_subscriptions(self) -> None:
        """Edit every subscribed message with the current status, pruning dead ones."""
        if self.schedule is None or not self.subscriptions:
            return

        embed = build_embed(self.schedule, set_at=self.set_at)
        survivors: list[dict] = []
        changed = False
        for sub in self.subscriptions:
            channel = self.bot.get_channel(sub["channel_id"])
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(sub["channel_id"])
                except (discord.NotFound, discord.Forbidden):
                    changed = True
                    continue
            try:
                message = await channel.fetch_message(sub["message_id"])
                await message.edit(embed=embed)
                survivors.append(sub)
            except discord.NotFound:
                changed = True  # message was deleted; drop the subscription
            except discord.Forbidden:
                survivors.append(sub)  # transient permission issue; keep it

        if changed:
            self.subscriptions[:] = survivors
            await self.save_state()

    @tasks.loop(seconds=UPDATE_INTERVAL_SECONDS)
    async def update_loop(self) -> None:
        await self.refresh_subscriptions()

    @update_loop.before_loop
    async def before_update_loop(self) -> None:
        await self.bot.wait_until_ready()

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
        if isinstance(error, app_commands.CheckFailure):
            msg = str(error) or "You don't have permission to use this command."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HangarCog(bot))
