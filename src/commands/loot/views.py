"""Persistent loot buttons, the Log loot modal, and the delete confirmation."""

from __future__ import annotations

import discord

from . import handlers


class _JoinButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Join", style=discord.ButtonStyle.primary, custom_id="loot:join")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await handlers.handle_card_join(self._cog, interaction)


class _LeaveButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Leave", style=discord.ButtonStyle.secondary, custom_id="loot:leave")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await handlers.handle_card_leave(self._cog, interaction)


class LootCardView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        self.add_item(_JoinButton(cog))
        self.add_item(_LeaveButton(cog))


class LogLootModal(discord.ui.Modal, title="Log loot"):
    commodity = discord.ui.TextInput(label="Commodity", placeholder="Gold", max_length=100)
    scu = discord.ui.TextInput(label="SCU", placeholder="96", max_length=7)

    def __init__(self, cog) -> None:
        super().__init__()
        self._cog = cog

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.scu.value.strip()
        if not raw.isdigit() or int(raw) == 0:
            await interaction.response.send_message("SCU must be a whole number above 0.", ephemeral=True)
            return
        await handlers.handle_log(
            self._cog,
            interaction,
            commodity=self.commodity.value,
            scu=int(raw),
            holder_id=interaction.user.id,
            raid=None,
        )


class _LogLootButton(discord.ui.Button):
    def __init__(self, cog) -> None:
        super().__init__(label="Log loot", style=discord.ButtonStyle.success, custom_id="loot:log")
        self._cog = cog

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(LogLootModal(self._cog))


class LogLootView(discord.ui.View):
    def __init__(self, cog) -> None:
        super().__init__(timeout=None)
        self.add_item(_LogLootButton(cog))


class ConfirmDeleteView(discord.ui.View):
    def __init__(self, cog, guild_id: int, loot_id: int) -> None:
        super().__init__(timeout=60)
        self._cog = cog
        self._guild_id = guild_id
        self._loot_id = loot_id

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await handlers.confirm_delete(self._cog, interaction, self._guild_id, self._loot_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Kept the raid.", view=None)
