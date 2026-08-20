"""Persistent claim/close buttons for beacon messages.

The legacy variant keeps the pre-rename ``tickets:`` custom ids alive so
buttons on messages posted before the beacon rename still respond.
"""

from __future__ import annotations

import discord

from . import lifecycle, scheduled


def _prefix(legacy: bool) -> str:
    return "tickets" if legacy else "beacons"


class _JoinButton(discord.ui.Button):
    def __init__(self, cog, legacy: bool) -> None:
        super().__init__(label="Join", style=discord.ButtonStyle.primary, custom_id=f"{_prefix(legacy)}:claim")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_join(self._cog, interaction)


class _LeaveButton(discord.ui.Button):
    def __init__(self, cog, legacy: bool) -> None:
        super().__init__(label="Leave", style=discord.ButtonStyle.secondary, custom_id=f"{_prefix(legacy)}:leave")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_leave(self._cog, interaction)


class _CloseButton(discord.ui.Button):
    def __init__(self, cog, legacy: bool) -> None:
        super().__init__(label="Close", style=discord.ButtonStyle.danger, custom_id=f"{_prefix(legacy)}:close")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_close(self._cog, interaction)


class BeaconView(discord.ui.View):
    def __init__(self, cog, legacy: bool = False) -> None:
        super().__init__(timeout=None)
        self.add_item(_JoinButton(cog, legacy))
        self.add_item(_LeaveButton(cog, legacy))
        self.add_item(_CloseButton(cog, legacy))


class _CommendButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Commend responders", style=discord.ButtonStyle.success, custom_id="beacons:commend")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_commend(self._cog, interaction)


class CommendView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        self.add_item(_CommendButton(cog))


class _ScheduledJoinButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Join", style=discord.ButtonStyle.primary, custom_id="beacons:sched_join")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await scheduled.handle_scheduled_join(self._cog, interaction)


class _ScheduledLeaveButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Leave", style=discord.ButtonStyle.secondary, custom_id="beacons:sched_leave")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await scheduled.handle_scheduled_leave(self._cog, interaction)


class _ScheduledCancelButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Cancel", style=discord.ButtonStyle.danger, custom_id="beacons:sched_cancel")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await scheduled.handle_scheduled_cancel(self._cog, interaction)


class ScheduledBeaconView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        self.add_item(_ScheduledJoinButton(cog))
        self.add_item(_ScheduledLeaveButton(cog))
        self.add_item(_ScheduledCancelButton(cog))
