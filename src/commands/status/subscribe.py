"""Handler for /status subscribe."""
from __future__ import annotations

import discord

from .constants import SUBSCRIPTIONS_KEY


async def handle(cog, interaction: discord.Interaction) -> None:
    if interaction.channel_id is None:
        await interaction.response.send_message(
            "This command can only be used in a channel.", ephemeral=True
        )
        return
    subscriptions = await cog.bot.state.get(SUBSCRIPTIONS_KEY, [])
    if interaction.channel_id in subscriptions:
        await interaction.response.send_message(
            "This channel is already subscribed to RSI status updates.", ephemeral=True
        )
        return
    subscriptions.append(interaction.channel_id)
    await cog.bot.state.set(SUBSCRIPTIONS_KEY, subscriptions)
    await interaction.response.send_message(
        "Subscribed — new RSI status updates will be posted here.", ephemeral=True
    )
