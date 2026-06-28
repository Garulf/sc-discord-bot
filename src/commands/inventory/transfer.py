"""Handler for /inventory transfer item."""

from __future__ import annotations

import discord

from .shared import ITEMS, get_guild_inventory, save_guild_inventory
from .subscriptions import refresh_live_status


async def handle(
    cog,
    interaction: discord.Interaction,
    recipient: discord.Member,
    entries: list[tuple[str, int]],
) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    if recipient.id == interaction.user.id:
        await interaction.response.send_message("You can't transfer cards to yourself.", ephemeral=True)
        return

    for card, count in entries:
        if card not in ITEMS:
            await interaction.response.send_message(
                f"**{card}** is not a valid DCHS item. Choose from DCHS-01 through DCHS-07.",
                ephemeral=True,
            )
            return
        if count < 1:
            await interaction.response.send_message("Count must be at least 1.", ephemeral=True)
            return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    sender_key = str(interaction.user.id)
    recipient_key = str(recipient.id)

    sender_inv = dict(guild_inv.get(sender_key, {}))

    totals: dict[str, int] = {}
    for card, count in entries:
        totals[card] = totals.get(card, 0) + count

    for card, count in totals.items():
        have = sender_inv.get(card, 0)
        if have < count:
            await interaction.response.send_message(
                f"You only have ×{have} **{card}** but tried to transfer ×{count}.",
                ephemeral=True,
            )
            return

    recipient_inv = dict(guild_inv.get(recipient_key, {}))

    for card, count in totals.items():
        sender_inv[card] = sender_inv[card] - count
        if sender_inv[card] == 0:
            del sender_inv[card]
        recipient_inv[card] = recipient_inv.get(card, 0) + count

    guild_inv[sender_key] = sender_inv
    guild_inv[recipient_key] = recipient_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    if len(totals) == 1:
        card, count = next(iter(totals.items()))
        msg = f"Transferred ×{count} **{card}** to {recipient.mention}."
    else:
        parts = ", ".join(f"×{count} **{card}**" for card, count in totals.items())
        msg = f"Transferred {parts} to {recipient.mention}."
    await interaction.response.send_message(msg, ephemeral=True)
    await refresh_live_status(cog, interaction.guild_id)
