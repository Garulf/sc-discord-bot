"""Intergalactic Aerospace Expo countdown: /iae countdown.

The countdown itself is a Discord relative timestamp, which every client
renders and ticks in the viewer's own time zone. The bot only edits a posted
widget when the expo changes phase (doors open, doors close).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from enum import StrEnum

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

EVENT_NAME = "IAE 2956"
OPENS_AT = datetime(2026, 11, 13, 16, 0, tzinfo=UTC)
CLOSES_AT = datetime(2026, 11, 27, 20, 0, tzinfo=UTC)
EVENT_URL = "https://robertsspaceindustries.com/en/comm-link/transmission/21389-Countdown-To-IAE-2956"
BANNER_URL = (
    "https://robertsspaceindustries.com/i/e55e5e144978e40380587dde85dda9e6c22701a5/"
    "resize(2048,1024,cover,ADdPNihJzmPbNuTnFsH1DqUeqBRpXdSXVVtgJTyDDgscGKrzJuoFjReskZdR2D6tvD6KpL1LMoQ5ujQgbNEu2wUSr)/"
    "source.jpg"
)

REFRESH_INTERVAL_SECONDS = 30

_STATE_KEY = "iae"
_EMBED_COLOR = 0x0099D6


class Phase(StrEnum):
    UPCOMING = "upcoming"
    OPEN = "open"
    ENDED = "ended"


def phase_at(now: datetime) -> Phase:
    if now < OPENS_AT:
        return Phase.UPCOMING
    if now < CLOSES_AT:
        return Phase.OPEN
    return Phase.ENDED


def _headline(phase: Phase) -> tuple[str, str]:
    opens = discord.utils.format_dt(OPENS_AT, "R")
    closes = discord.utils.format_dt(CLOSES_AT, "R")
    if phase is Phase.UPCOMING:
        return f"Countdown to {EVENT_NAME}", f"Doors open {opens}"
    if phase is Phase.OPEN:
        return f"{EVENT_NAME} is open", f"Doors close {closes}"
    return f"{EVENT_NAME} has ended", f"Doors closed {closes}"


def build_embed(now: datetime) -> discord.Embed:
    title, description = _headline(phase_at(now))
    embed = discord.Embed(title=title, description=description, url=EVENT_URL, color=_EMBED_COLOR)
    embed.add_field(name="Opens", value=discord.utils.format_dt(OPENS_AT, "F"))
    embed.add_field(name="Closes", value=discord.utils.format_dt(CLOSES_AT, "F"))
    embed.set_image(url=BANNER_URL)
    return embed


class IaeCog(commands.Cog):
    """Countdown widgets for the Intergalactic Aerospace Expo."""

    iae = app_commands.Group(name="iae", description="Intergalactic Aerospace Expo")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.widgets: list[dict] = []

    async def cog_load(self) -> None:
        data = await self.bot.state.get(_STATE_KEY) or {}
        self.widgets = data.get("widgets", [])
        self.refresh_loop.start()

    async def cog_unload(self) -> None:
        self.refresh_loop.cancel()

    async def _save(self) -> None:
        await self.bot.state.set(_STATE_KEY, {"widgets": self.widgets})

    @tasks.loop(seconds=REFRESH_INTERVAL_SECONDS)
    async def refresh_loop(self) -> None:
        await self.refresh_widgets(datetime.now(UTC))

    @refresh_loop.before_loop
    async def before_refresh_loop(self) -> None:
        await self.bot.wait_until_ready()

    @refresh_loop.error
    async def refresh_loop_error(self, error: Exception) -> None:
        logger.exception("IAE refresh loop stopped unexpectedly: %s", error)

    def _message(self, widget: dict) -> discord.PartialMessage:
        return self.bot.get_partial_messageable(widget["channel_id"]).get_partial_message(widget["message_id"])

    def _forget(self, widget: dict) -> None:
        if widget in self.widgets:
            self.widgets.remove(widget)

    async def refresh_widgets(self, now: datetime) -> None:
        """Re-render every widget whose phase is out of date.

        A widget is dropped once it shows the ended state (nothing left to
        update) or when its message is gone or out of the bot's reach.
        """
        phase = phase_at(now)
        stale = [widget for widget in self.widgets if widget["phase"] != phase.value]
        if not stale:
            return

        embed = build_embed(now)
        changed = False
        for widget in stale:
            try:
                await self._message(widget).edit(embed=embed)
            except (discord.NotFound, discord.Forbidden):
                self._forget(widget)
                changed = True
                continue
            except discord.HTTPException as exc:
                logger.warning("Failed to update IAE widget %s: %s", widget, exc)
                continue
            if phase is Phase.ENDED:
                self._forget(widget)
            else:
                widget["phase"] = phase.value
            changed = True

        if changed:
            await self._save()

    async def _retire_widgets_in(self, channel_id: int) -> None:
        for widget in [w for w in self.widgets if w["channel_id"] == channel_id]:
            self._forget(widget)
            try:
                await self._message(widget).delete()
            except discord.HTTPException:
                pass

    async def post_widget(self, interaction: discord.Interaction, now: datetime) -> None:
        await interaction.response.send_message(embed=build_embed(now))
        phase = phase_at(now)
        if phase is Phase.ENDED:
            return
        message = await interaction.original_response()
        await self._retire_widgets_in(interaction.channel_id)
        self.widgets.append({"channel_id": interaction.channel_id, "message_id": message.id, "phase": phase.value})
        await self._save()

    @iae.command(name="countdown", description="Post a live countdown to the Intergalactic Aerospace Expo here")
    async def countdown(self, interaction: discord.Interaction) -> None:
        await self.post_widget(interaction, datetime.now(UTC))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(IaeCog(bot))
