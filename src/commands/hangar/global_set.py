"""Handler for /hangar global set (bot owner only)."""

from __future__ import annotations

from datetime import UTC, datetime

import discord
from discord import app_commands

from src.exec_hangars import HangarSchedule

from .shared import build_embed, refresh_subscriptions, save_state
from .warnings import refresh_event_messages


async def handle(
    cog,
    interaction: discord.Interaction,
    phase: app_commands.Choice[str],
    lights: int,
) -> None:
    now = datetime.now(UTC)
    if phase.value == "charging":
        cog.global_schedule = HangarSchedule.from_charging(lights_green=lights, observed_at=now)
    elif phase.value == "active":
        cog.global_schedule = HangarSchedule.from_active(lights_expired=lights, observed_at=now)
    else:
        cog.global_schedule = HangarSchedule.from_reset(observed_at=now)

    cog.global_set_at = now

    # Reset warning state for subscriptions that use the global schedule (no guild override).
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

    await save_state(cog)
    await interaction.response.send_message(
        "Global hangar state updated. Servers without a local override will use this schedule.",
        embed=build_embed(cog.global_schedule, now, set_at=cog.global_set_at),
        ephemeral=True,
    )
    await refresh_subscriptions(cog)
    await refresh_event_messages(cog)
