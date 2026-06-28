"""Subscription state, live-status updates, and notifications for /inventory."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import discord

from .image import build_status_image
from .shared import build_status_table, get_guild_inventory

logger = logging.getLogger(__name__)

_SUB_KEY_PREFIX = "inventory_subscriptions"
NOTIFICATION_LIFETIME = timedelta(hours=12)
_MAX_NOTIFICATIONS_PER_CHANNEL = 5
_BUMP_EXPIRY = timedelta(hours=1)


def _sub_key(guild_id: int) -> str:
    return f"{_SUB_KEY_PREFIX}:{guild_id}"


async def get_guild_subs(cog, guild_id: int) -> dict:
    result = await cog.bot.state.get(_sub_key(guild_id), {"subscriptions": [], "notifications": []})
    if result is None:
        return {"subscriptions": [], "notifications": []}
    return result


async def save_guild_subs(cog, guild_id: int, data: dict) -> None:
    await cog.bot.state.set(_sub_key(guild_id), data)


# ---------------------------------------------------------------------------
# Live-status embed
# ---------------------------------------------------------------------------

_HEADER = "**DCHS Inventory Status**"


async def _build_live_content(cog, guild: discord.Guild) -> tuple[str, discord.File | None]:
    guild_inv = await get_guild_inventory(cog, guild.id)
    active = {uid: inv for uid, inv in guild_inv.items() if inv}

    member_names: dict[str, str] = {}
    for user_key in active:
        member = guild.get_member(int(user_key))
        if member is None:
            try:
                member = await guild.fetch_member(int(user_key))
            except (discord.NotFound, discord.HTTPException):
                continue
        member_names[user_key] = member.display_name

    table = build_status_table(active, member_names)
    if table:
        return _HEADER, discord.File(build_status_image(table), filename="status.png")
    return f"{_HEADER}\n*No inventory data yet.*", None


async def refresh_live_status(cog, guild_id: int) -> None:
    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return
    data = await get_guild_subs(cog, guild_id)
    if not data["subscriptions"]:
        return
    logger.info("Refreshing %d inventory subscription(s) for guild %d", len(data["subscriptions"]), guild_id)

    content, file = await _build_live_content(cog, guild)
    survivors = []
    changed = False

    for sub in data["subscriptions"]:
        channel = cog.bot.get_channel(sub["channel_id"])
        if channel is None:
            try:
                channel = await cog.bot.fetch_channel(sub["channel_id"])
            except (discord.NotFound, discord.Forbidden):
                changed = True
                continue
            except discord.HTTPException as exc:
                logger.warning("Failed to fetch channel %s: %s", sub["channel_id"], exc)
                survivors.append(sub)
                continue
        try:
            message = await channel.fetch_message(sub["message_id"])
            if file is not None:
                file.fp.seek(0)
                await message.edit(content=content, embed=None, attachments=[file])
            else:
                await message.edit(content=content, embed=None, attachments=[])
            survivors.append(sub)
        except discord.NotFound:
            changed = True
        except discord.Forbidden:
            survivors.append(sub)
        except discord.HTTPException as exc:
            logger.warning("Failed to update live status in %s: %s", sub["channel_id"], exc)
            survivors.append(sub)

    if changed:
        data["subscriptions"] = survivors
        await save_guild_subs(cog, guild_id, data)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def _trim_channel_notifications(data: dict, channel_id: int, now: datetime) -> None:
    """Cap per-channel notifications at _MAX_NOTIFICATIONS_PER_CHANNEL.

    Notifications bumped out of the top 5 get their expiry reduced to 1 hour
    from now (or keep their existing expiry if it's already sooner).
    """
    channel_notifs = [n for n in data["notifications"] if n["channel_id"] == channel_id]
    if len(channel_notifs) <= _MAX_NOTIFICATIONS_PER_CHANNEL:
        return
    channel_notifs.sort(key=lambda n: n["message_id"])
    bump_expires = now + _BUMP_EXPIRY
    excess = channel_notifs[: len(channel_notifs) - _MAX_NOTIFICATIONS_PER_CHANNEL]
    for notif in excess:
        current = datetime.fromisoformat(notif["expires_at"])
        if current > bump_expires:
            notif["expires_at"] = bump_expires.isoformat()


async def notify_added(
    cog,
    guild_id: int,
    user: discord.Member,
    sets_before: int,
    sets_after: int,
    pool_before: int,
    pool_after: int,
) -> None:
    data = await get_guild_subs(cog, guild_id)
    if not data["subscriptions"]:
        return

    messages = []
    if sets_after > sets_before:
        gained = sets_after - sets_before
        messages.append(
            f"🏆 **{user.display_name}** completed {'a' if gained == 1 else str(gained)} "
            f"DCHS set{'s' if gained != 1 else ''}!"
        )
    if pool_after > pool_before and sets_after == sets_before:
        gained = pool_after - pool_before
        messages.append(
            f"🎉 The server pool has reached **{pool_after} complete set{'s' if pool_after != 1 else ''}**!"
        )

    if not messages:
        return

    now = datetime.now(UTC)
    expires_at = (now + NOTIFICATION_LIFETIME).isoformat()
    changed = False

    for sub in data["subscriptions"]:
        channel = cog.bot.get_channel(sub["channel_id"])
        if channel is None:
            try:
                channel = await cog.bot.fetch_channel(sub["channel_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue

        for text in messages:
            try:
                msg = await channel.send(text)
                data["notifications"].append(
                    {
                        "channel_id": sub["channel_id"],
                        "message_id": msg.id,
                        "expires_at": expires_at,
                    }
                )
                _trim_channel_notifications(data, sub["channel_id"], now)
                changed = True
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("Failed to post inventory notification to %s: %s", sub["channel_id"], exc)

    if changed:
        await save_guild_subs(cog, guild_id, data)


async def notify_transfer(
    cog,
    guild_id: int,
    sender: discord.Member,
    recipient: discord.Member,
    entries: list[tuple[str, int]] | None,
) -> None:
    """Post a transfer notification to all subscribed channels.

    Pass entries=None to indicate a full set transfer.
    """
    data = await get_guild_subs(cog, guild_id)
    if not data["subscriptions"]:
        return

    if entries is None:
        text = f"{sender.mention} transferred a complete set (DCHS-01 through DCHS-07) to {recipient.mention}."
    elif len(entries) == 1:
        card, count = entries[0]
        text = f"{sender.mention} transferred ×{count} **{card}** to {recipient.mention}."
    else:
        parts = ", ".join(f"×{count} **{card}**" for card, count in entries)
        text = f"{sender.mention} transferred {parts} to {recipient.mention}."

    now = datetime.now(UTC)
    expires_at = (now + NOTIFICATION_LIFETIME).isoformat()
    changed = False

    for sub in data["subscriptions"]:
        channel = cog.bot.get_channel(sub["channel_id"])
        if channel is None:
            try:
                channel = await cog.bot.fetch_channel(sub["channel_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        try:
            msg = await channel.send(text)
            data["notifications"].append(
                {
                    "channel_id": sub["channel_id"],
                    "message_id": msg.id,
                    "expires_at": expires_at,
                }
            )
            _trim_channel_notifications(data, sub["channel_id"], now)
            changed = True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("Failed to post transfer notification to %s: %s", sub["channel_id"], exc)

    if changed:
        await save_guild_subs(cog, guild_id, data)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


async def cleanup_expired_notifications(cog, guild_id: int) -> None:
    data = await get_guild_subs(cog, guild_id)
    if not data["notifications"]:
        return

    now = datetime.now(UTC)
    survivors = []
    changed = False

    for notif in data["notifications"]:
        expires_at = datetime.fromisoformat(notif["expires_at"])
        if now < expires_at:
            survivors.append(notif)
            continue
        channel = cog.bot.get_channel(notif["channel_id"])
        if channel is None:
            try:
                channel = await cog.bot.fetch_channel(notif["channel_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                changed = True
                continue
        try:
            msg = await channel.fetch_message(notif["message_id"])
            await msg.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
        changed = True

    if changed:
        data["notifications"] = survivors
        await save_guild_subs(cog, guild_id, data)
