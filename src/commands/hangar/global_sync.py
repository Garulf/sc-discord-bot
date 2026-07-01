"""Handler for /hangar global sync (bot owner only)."""

from __future__ import annotations

from datetime import UTC, datetime

import discord

from .shared import build_embed, refresh_subscriptions, save_state
from .sync import _build_schedule, parse_sync
from .warnings import refresh_event_messages


async def _reset_global_notify(cog) -> None:
    """Delete notify messages and clear state for subscriptions on the global schedule."""
    for sub in cog.subscriptions:
        sub_guild = sub.get("guild_id")
        if sub_guild is None or sub_guild not in cog.guild_schedules:
            old_mid = sub.get("notify_message_id")
            if old_mid is not None:
                ch = cog.bot.get_channel(sub["channel_id"])
                if ch:
                    try:
                        msg = await ch.fetch_message(old_mid)
                        await msg.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
            sub["notify_state"] = None
            sub["notify_message_id"] = None


async def handle(cog, interaction: discord.Interaction, timestamp: str) -> None:
    try:
        phase, observed_at = parse_sync(timestamp)
    except ValueError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    now = datetime.now(UTC)
    cog.global_schedule = _build_schedule(phase, observed_at)
    cog.global_set_at = now

    await _reset_global_notify(cog)
    await save_state(cog)

    await interaction.response.send_message(
        "Global hangar synced.",
        embed=build_embed(cog.global_schedule, now, set_at=cog.global_set_at),
        ephemeral=True,
    )
    await refresh_subscriptions(cog)
    await refresh_event_messages(cog)
