"""Personal countdown timers for Star Citizen in-game events.

Timers are ephemeral to the requesting user: the start/cancel responses are
only visible to them, and the expiry notification arrives as a DM.

Discord interaction tokens expire after 15 minutes, which is shorter than
either timer, so followup messages cannot be used — DMs are the only
private channel available at notification time.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

_TIMERS: dict[str, tuple[str, int]] = {
    "keycard": ("Key Card", 30),
    "vault": ("Ghost Arena Vault Door", 20),
}

_CHOICES = [
    app_commands.Choice(name=f"{label} ({minutes} min)", value=key)
    for key, (label, minutes) in _TIMERS.items()
]

_REDO_TIMEOUT = 300  # seconds the "Redo Timer" button stays active


class RestartTimerView(discord.ui.View):
    """DM view with a 'Redo Timer' button sent when a timer expires."""

    def __init__(self, cog: TimerCog, user_id: int, key: str, label: str, minutes: int) -> None:
        super().__init__(timeout=_REDO_TIMEOUT)
        self._cog = cog
        self._user_id = user_id
        self._key = key
        self._label = label
        self._minutes = minutes
        self.message: discord.Message | None = None

    async def _handle_redo(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self._cog._cancel_existing(self._user_id, self._key)
        task = asyncio.create_task(
            self._cog._run(self._user_id, self._key, self._label, self._minutes * 60)
        )
        self._cog._tasks[(self._user_id, self._key)] = task

        button.disabled = True
        self.stop()

        expires = datetime.now(timezone.utc) + timedelta(minutes=self._minutes)
        await interaction.response.edit_message(
            content=(
                f"⏰ **{self._label}** timer is up!\n"
                f"⏱️ Restarted — {self._minutes} min ({discord.utils.format_dt(expires, 'R')})"
            ),
            view=self,
        )

    @discord.ui.button(label="Redo Timer", style=discord.ButtonStyle.primary, emoji="⏱️")
    async def redo(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self._handle_redo(interaction, button)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[union-attr]
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


class TimerCog(commands.Cog):
    """Personal countdown timers for Star Citizen in-game events."""

    timer = app_commands.Group(name="timer", description="Personal countdown timers")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._tasks: dict[tuple[int, str], asyncio.Task] = {}

    def _cancel_existing(self, user_id: int, key: str) -> bool:
        """Cancel any running task for (user_id, key). Returns True if one was found."""
        task = self._tasks.pop((user_id, key), None)
        if task and not task.done():
            task.cancel()
            return True
        return False

    async def _notify(self, user_id: int, key: str, label: str, minutes: int) -> None:
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            view = RestartTimerView(self, user_id, key, label, minutes)
            view.message = await user.send(f"⏰ **{label}** timer is up!", view=view)
        except discord.Forbidden:
            logger.warning("Cannot DM user %d — DMs are disabled", user_id)
        except Exception:
            logger.exception("Failed to notify user %d", user_id)

    async def _run(self, user_id: int, key: str, label: str, seconds: int) -> None:
        try:
            await asyncio.sleep(seconds)
            await self._notify(user_id, key, label, seconds // 60)
        except asyncio.CancelledError:
            pass
        finally:
            self._tasks.pop((user_id, key), None)

    async def _start(self, interaction: discord.Interaction, key: str) -> None:
        label, minutes = _TIMERS[key]
        user_id = interaction.user.id
        restarted = self._cancel_existing(user_id, key)

        task = asyncio.create_task(self._run(user_id, key, label, minutes * 60))
        self._tasks[(user_id, key)] = task

        expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        prefix = "Restarted — " if restarted else ""
        await interaction.response.send_message(
            f"⏱️ {prefix}**{label}** — {minutes} min "
            f"({discord.utils.format_dt(expires, 'R')})\n"
            "I'll DM you when it's up.",
            ephemeral=True,
        )

    @timer.command(name="keycard", description="Start a 30-minute key card reset timer")
    async def keycard(self, interaction: discord.Interaction) -> None:
        await self._start(interaction, "keycard")

    @timer.command(name="vault", description="Start a 20-minute Ghost Arena vault door timer")
    async def vault(self, interaction: discord.Interaction) -> None:
        await self._start(interaction, "vault")

    @timer.command(name="cancel", description="Cancel an active timer")
    @app_commands.describe(kind="Which timer to cancel")
    @app_commands.choices(kind=_CHOICES)
    async def cancel(self, interaction: discord.Interaction, kind: str) -> None:
        label, _ = _TIMERS[kind]
        if self._cancel_existing(interaction.user.id, kind):
            await interaction.response.send_message(
                f"✅ Cancelled your **{label}** timer.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"No active **{label}** timer found.", ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TimerCog(bot))
