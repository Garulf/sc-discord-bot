"""Handler for /hangar unsubscribe."""

from __future__ import annotations

import discord

from .shared import save_state


async def handle(cog, interaction: discord.Interaction) -> None:
    channel_id = interaction.channel_id
    removed = [sub for sub in cog.subscriptions if sub["channel_id"] == channel_id]
    if not removed:
        await interaction.response.send_message("There's no live status in this channel.", ephemeral=True)
        return

    cog.subscriptions[:] = [sub for sub in cog.subscriptions if sub["channel_id"] != channel_id]
    await save_state(cog)
    for sub in removed:
        for msg_id in (sub["message_id"], sub.get("notify_message_id")):
            if msg_id is None:
                continue
            try:
                message = await interaction.channel.fetch_message(msg_id)
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
    await interaction.response.send_message(f"Removed {len(removed)} live status message(s).", ephemeral=True)
