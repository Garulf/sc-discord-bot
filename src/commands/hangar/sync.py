"""Handler for /hangar sync."""

from __future__ import annotations

from datetime import UTC, datetime

import discord

from src.exec_hangars import HangarSchedule

from .shared import build_embed, get_schedule_for_guild, refresh_subscriptions, save_state
from .warnings import refresh_event_messages

_PHASE_MAP = {
    "open": "active",
    "closed": "charging",
    "resetting": "reset",
}

_DT_FORMAT = "%m/%d/%Y, %I:%M:%S %p"


def parse_sync(text: str) -> tuple[str, datetime]:
    """Parse 'Open     7/1/2026, 4:11:31 AM' → (phase, utc_datetime)."""
    parts = text.split(None, 1)
    if len(parts) != 2:
        raise ValueError("Expected format: `Open 7/1/2026, 4:11:31 AM`")
    phase_word = parts[0].lower()
    if phase_word not in _PHASE_MAP:
        valid = ", ".join(f"`{k.title()}`" for k in _PHASE_MAP)
        raise ValueError(f"Unknown phase **{parts[0]}**. Expected one of: {valid}.")
    try:
        dt = datetime.strptime(parts[1].strip(), _DT_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        raise ValueError(f"Couldn't parse **{parts[1].strip()}**. Expected `M/D/YYYY, H:MM:SS AM/PM` (UTC).")
    return _PHASE_MAP[phase_word], dt


def _build_schedule(phase: str, observed_at: datetime) -> HangarSchedule:
    if phase == "active":
        return HangarSchedule.from_active(lights_expired=0, observed_at=observed_at)
    if phase == "charging":
        return HangarSchedule.from_charging(lights_green=0, observed_at=observed_at)
    return HangarSchedule.from_reset(observed_at=observed_at)


async def _reset_notify(cog, guild_id: int) -> None:
    """Delete the old notify message and clear notify state for guild subscriptions."""
    for sub in cog.subscriptions:
        if sub.get("guild_id") == guild_id:
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
    guild_id = interaction.guild_id
    cog.guild_schedules[guild_id] = _build_schedule(phase, observed_at)
    cog.guild_set_at[guild_id] = now

    await _reset_notify(cog, guild_id)
    await save_state(cog)

    schedule, set_at = get_schedule_for_guild(cog, guild_id)
    await interaction.response.send_message(
        "Hangar synced.",
        embed=build_embed(schedule, now, set_at=set_at),
        ephemeral=True,
    )
    await refresh_subscriptions(cog)
    await refresh_event_messages(cog)
