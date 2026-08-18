"""Persistent button views for the ticket panel and ticket messages."""

from __future__ import annotations

import discord

from . import lifecycle
from .categories import CATEGORIES
from .modals import TicketModal


class _PanelButton(discord.ui.Button):
    def __init__(self, cog, category_key: str) -> None:
        category = CATEGORIES[category_key]
        super().__init__(
            label=category.label,
            emoji=category.emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"tickets:panel:{category_key}",
        )
        self._cog = cog
        self._category_key = category_key

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(TicketModal(self._cog, self._category_key))


class PanelView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        for key in CATEGORIES:
            self.add_item(_PanelButton(cog, key))


class _ClaimButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Claim", style=discord.ButtonStyle.primary, custom_id="tickets:claim")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_claim(self._cog, interaction)


class _CloseButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Close", style=discord.ButtonStyle.danger, custom_id="tickets:close")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await lifecycle.handle_close(self._cog, interaction)


class TicketView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        self.add_item(_ClaimButton(cog))
        self.add_item(_CloseButton(cog))
