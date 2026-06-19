"""Handler for /status unsubscribe."""

from __future__ import annotations

import discord

from .constants import SUBSCRIPTIONS_KEY


async def handle(cog, interaction: discord.Interaction) -> None:
    subscriptions = await cog.bot.state.get(SUBSCRIPTIONS_KEY, [])
    if interaction.channel_id not in subscriptions:
        await interaction.response.send_message("This channel isn't subscribed to RSI status updates.", ephemeral=True)
        return
    subscriptions = [c for c in subscriptions if c != interaction.channel_id]
    await cog.bot.state.set(SUBSCRIPTIONS_KEY, subscriptions)
    await interaction.response.send_message("Unsubscribed from RSI status updates.", ephemeral=True)
