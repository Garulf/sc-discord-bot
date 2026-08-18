"""Persistent claim/close buttons for beacon messages.

The legacy variant keeps the pre-rename ``tickets:`` custom ids alive so
buttons on messages posted before the beacon rename still respond.
"""

from __future__ import annotations

import discord

from . import lifecycle


def _prefix(legacy: bool) -> str:
    return "tickets" if legacy else "beacons"


class _ClaimButton(discord.ui.Button):
    def __init__(self, cog, legacy: bool) -> None:
        super().__init__(label="Claim", style=discord.ButtonStyle.primary, custom_id=f"{_prefix(legacy)}:claim")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_claim(self._cog, interaction)


class _CloseButton(discord.ui.Button):
    def __init__(self, cog, legacy: bool) -> None:
        super().__init__(label="Close", style=discord.ButtonStyle.danger, custom_id=f"{_prefix(legacy)}:close")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_close(self._cog, interaction)


class BeaconView(discord.ui.View):
    def __init__(self, cog, legacy: bool = False) -> None:
        super().__init__(timeout=None)
        self.add_item(_ClaimButton(cog, legacy))
        self.add_item(_CloseButton(cog, legacy))
