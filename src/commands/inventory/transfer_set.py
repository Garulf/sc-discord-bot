"""Handler for /inventory transfer set."""

from __future__ import annotations

import discord

from .shared import ITEMS, complete_sets, get_guild_inventory, save_guild_inventory
from .subscriptions import refresh_live_status


async def handle(cog, interaction: discord.Interaction, recipient: discord.Member) -> None:
    if interaction.guild_id is None:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return

    if recipient.id == interaction.user.id:
        await interaction.response.send_message("You can't transfer a set to yourself.", ephemeral=True)
        return

    guild_inv = await get_guild_inventory(cog, interaction.guild_id)
    sender_key = str(interaction.user.id)
    recipient_key = str(recipient.id)

    sender_inv = dict(guild_inv.get(sender_key, {}))

    if complete_sets(sender_inv) < 1:
        await interaction.response.send_message("You don't have a complete set to transfer.", ephemeral=True)
        return

    recipient_inv = dict(guild_inv.get(recipient_key, {}))
    recipient_sets_before = complete_sets(recipient_inv)
    pool_before = pool_sets(guild_inv)

    for item in ITEMS:
        sender_inv[item] = sender_inv[item] - 1
        if sender_inv[item] == 0:
            del sender_inv[item]
        recipient_inv[item] = recipient_inv.get(item, 0) + 1

    guild_inv[sender_key] = sender_inv
    guild_inv[recipient_key] = recipient_inv
    await save_guild_inventory(cog, interaction.guild_id, guild_inv)

    await interaction.response.send_message(
        f"Transferred one complete set (DCHS-01 through DCHS-07) to {recipient.mention}.",
        ephemeral=True,
    )
    await refresh_live_status(cog, interaction.guild_id)
