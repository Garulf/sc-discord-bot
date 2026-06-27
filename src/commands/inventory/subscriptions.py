"""Subscription state, live-status updates, and notifications for /inventory."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import discord

from .shared import complete_sets, format_field, get_guild_inventory

logger = logging.getLogger(__name__)

_SUB_KEY_PREFIX = "inventory_subscriptions"
NOTIFICATION_LIFETIME = timedelta(hours=12)


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

async def _build_live_embed(cog, guild: discord.Guild) -> discord.Embed:
    guild_inv = await get_guild_inventory(cog, guild.id)
    active = {uid: inv for uid, inv in guild_inv.items() if inv}

    pooled: dict[str, int] = {}
    for inv in active.values():
        for item, count in inv.items():
            pooled[item] = pooled.get(item, 0) + count
    total_sets = complete_sets(pooled)

    embed = discord.Embed(
        title="DCHS Inventory Status",
        color=0x57F287 if total_sets > 0 else 0x5865F2,
    )
    embed.set_footer(text=f"Server total: {total_sets} complete set{'s' if total_sets != 1 else ''}")

    shown = 0
    for user_key, user_inv in sorted(active.items(), key=lambda kv: complete_sets(kv[1]), reverse=True):
        if shown >= 25:
            break
        member = guild.get_member(int(user_key))
        if member is None:
            try:
                member = await guild.fetch_member(int(user_key))
            except (discord.NotFound, discord.HTTPException):
                continue
        embed.add_field(name=member.display_name, value=format_field(user_inv), inline=False)
        shown += 1

    if not shown:
        embed.description = "*No inventory data yet.*"

    return embed


async def refresh_live_status(cog, guild_id: int) -> None:
    guild = cog.bot.get_guild(guild_id)
    if guild is None:
        return
    data = await get_guild_subs(cog, guild_id)
    if not data["subscriptions"]:
        return

    embed = await _build_live_embed(cog, guild)
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
            await message.edit(embed=embed)
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

def _format_added(entries: list[tuple[str, int]]) -> str:
    return ", ".join(f"{item}×{count}" for item, count in entries)


async def notify_added(
    cog,
    guild_id: int,
    user: discord.Member,
    entries: list[tuple[str, int]],
    sets_before: int,
    sets_after: int,
) -> None:
    data = await get_guild_subs(cog, guild_id)
    if not data["subscriptions"]:
        return

    messages = [f"**{user.display_name}** has added {_format_added(entries)} to their inventory!"]
    if sets_after > sets_before:
        gained = sets_after - sets_before
        messages.append(
            f"🏆 **{user.display_name}** completed {'a' if gained == 1 else str(gained)} "
            f"DCHS set{'s' if gained != 1 else ''}!"
        )

    expires_at = (datetime.now(UTC) + NOTIFICATION_LIFETIME).isoformat()
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
                data["notifications"].append({
                    "channel_id": sub["channel_id"],
                    "message_id": msg.id,
                    "expires_at": expires_at,
                })
                changed = True
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("Failed to post inventory notification to %s: %s", sub["channel_id"], exc)

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
