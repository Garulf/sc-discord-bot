"""User context menu command: Transfer Set."""

from __future__ import annotations

import discord

from .shared import ITEMS, complete_sets, get_guild_inventory, save_guild_inventory
from .subscriptions import notify_transfer, refresh_live_status


def _cog(interaction: discord.Interaction):
    return interaction.client.cogs["InventoryCog"]


class ConfirmView(discord.ui.View):
    def __init__(self, sender: discord.Member, recipient: discord.Member) -> None:
        super().__init__(timeout=60)
        self.sender = sender
        self.recipient = recipient

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.sender.id:
            await interaction.response.send_message("This isn't your confirmation.", ephemeral=True)
            return

        self.stop()
        cog = _cog(interaction)

        guild_inv = await get_guild_inventory(cog, interaction.guild_id)
        sender_key = str(self.sender.id)
        recipient_key = str(self.recipient.id)
        sender_inv = dict(guild_inv.get(sender_key, {}))

        if complete_sets(sender_inv) < 1:
            await interaction.response.edit_message(content="You no longer have a complete set to transfer.", view=None)
            return

        recipient_inv = dict(guild_inv.get(recipient_key, {}))
        for item in ITEMS:
            sender_inv[item] = sender_inv[item] - 1
            if sender_inv[item] == 0:
                del sender_inv[item]
            recipient_inv[item] = recipient_inv.get(item, 0) + 1

        guild_inv[sender_key] = sender_inv
        guild_inv[recipient_key] = recipient_inv
        await save_guild_inventory(cog, interaction.guild_id, guild_inv)

        await interaction.response.edit_message(
            content=f"Transferred one complete set to {self.recipient.mention}.",
            view=None,
        )
        await notify_transfer(cog, interaction.guild_id, self.sender, self.recipient, None)
        await refresh_live_status(cog, interaction.guild_id)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(content="Transfer cancelled.", view=None)

    async def on_timeout(self) -> None:
        self.stop()


async def handle(interaction: discord.Interaction, member: discord.Member) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    if member.id == interaction.user.id:
        await interaction.response.send_message("You can't transfer a set to yourself.", ephemeral=True)
        return
    if member.bot:
        await interaction.response.send_message("You can't transfer a set to a bot.", ephemeral=True)
        return

    cog = _cog(interaction)
    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    sender_inv = guild_inv.get(str(interaction.user.id), {})
    if complete_sets(sender_inv) < 1:
        await interaction.response.send_message("You don't have a complete set to transfer.", ephemeral=True)
        return

    view = ConfirmView(sender=interaction.user, recipient=member)
    await interaction.response.send_message(
        f"Transfer one complete set (DCHS-01 through DCHS-07) to {member.mention}?",
        view=view,
        ephemeral=True,
    )
