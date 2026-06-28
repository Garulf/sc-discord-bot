"""User context menu command: Transfer Cards."""

from __future__ import annotations

import re

import discord
from discord import app_commands

from .shared import ITEMS, get_guild_inventory, save_guild_inventory
from .subscriptions import refresh_live_status

_ENTRY_RE = re.compile(r"dchs-0?([1-7])(?::(\d+))?", re.IGNORECASE)


def _parse_entries(text: str) -> list[tuple[str, int]] | str:
    """Parse 'dchs-01:2 dchs-04:1' into [(card, count), ...]. Returns error string on failure."""
    entries: dict[str, int] = {}
    for token in text.split():
        m = _ENTRY_RE.fullmatch(token.strip())
        if not m:
            return f"Could not parse `{token}`. Use format like `dchs-01:2 dchs-04:1`."
        card = f"DCHS-0{m.group(1)}"
        count = int(m.group(2)) if m.group(2) else 1
        if count < 1:
            return "Count must be at least 1."
        entries[card] = entries.get(card, 0) + count
    if not entries:
        return "Please specify at least one card."
    return list(entries.items())


class TransferModal(discord.ui.Modal, title="Transfer Cards"):
    cards = discord.ui.TextInput(
        label="Cards to transfer",
        placeholder="dchs-01:2  dchs-04:1  dchs-07:1",
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, recipient: discord.Member) -> None:
        super().__init__()
        self.recipient = recipient

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        parsed = _parse_entries(self.cards.value)
        if isinstance(parsed, str):
            await interaction.response.send_message(parsed, ephemeral=True)
            return

        guild_inv = await get_guild_inventory(interaction.client, interaction.guild_id)
        sender_key = str(interaction.user.id)
        recipient_key = str(self.recipient.id)
        sender_inv = dict(guild_inv.get(sender_key, {}))

        for card, count in parsed:
            have = sender_inv.get(card, 0)
            if have < count:
                await interaction.response.send_message(
                    f"You only have ×{have} **{card}** but tried to transfer ×{count}.",
                    ephemeral=True,
                )
                return

        recipient_inv = dict(guild_inv.get(recipient_key, {}))
        for card, count in parsed:
            sender_inv[card] = sender_inv[card] - count
            if sender_inv[card] == 0:
                del sender_inv[card]
            recipient_inv[card] = recipient_inv.get(card, 0) + count

        guild_inv[sender_key] = sender_inv
        guild_inv[recipient_key] = recipient_inv
        await save_guild_inventory(interaction.client, interaction.guild_id, guild_inv)

        if len(parsed) == 1:
            card, count = parsed[0]
            msg = f"Transferred ×{count} **{card}** to {self.recipient.mention}."
        else:
            parts = ", ".join(f"×{count} **{card}**" for card, count in parsed)
            msg = f"Transferred {parts} to {self.recipient.mention}."
        await interaction.response.send_message(msg, ephemeral=True)
        await refresh_live_status(interaction.client, interaction.guild_id)


async def handle(interaction: discord.Interaction, member: discord.Member) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    if member.id == interaction.user.id:
        await interaction.response.send_message("You can't transfer cards to yourself.", ephemeral=True)
        return
    if member.bot:
        await interaction.response.send_message("You can't transfer cards to a bot.", ephemeral=True)
        return
    await interaction.response.send_modal(TransferModal(recipient=member))
