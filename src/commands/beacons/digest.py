"""Weekly beacon digest: a summary embed posted to a configured channel."""

from __future__ import annotations

import logging
from typing import Any

import discord

from . import store
from .stats import _by_category_lines, _leaderboard_lines, compute_stats

logger = logging.getLogger(__name__)

WEEK_SECONDS = 7 * 24 * 3600


def build_digest_embed(stats: dict[str, Any], since: float) -> discord.Embed:
    embed = discord.Embed(title="Weekly Beacon Digest", color=discord.Color.blurple())
    embed.add_field(
        name="Overview",
        value=f"Opened: {stats['total']}\nClosed: {stats['closed']}",
        inline=False,
    )
    embed.add_field(name="By Category", value=_by_category_lines(stats["by_category"]), inline=False)
    embed.add_field(name="Top Responders", value=_leaderboard_lines(stats["top_responders"]), inline=True)
    embed.add_field(name="Top Commended", value=_leaderboard_lines(stats["top_commended"]), inline=True)
    return embed


async def maybe_post_digest(cog, guild, now: float) -> None:
    config = await store.get_config(cog.bot.state, guild.id)
    settings = store.get_settings(config)
    digest_channel_id = settings["digest_channel_id"]
    if not digest_channel_id:
        return
    if config.get("last_digest_at", 0) > now - WEEK_SECONDS:
        return

    since = now - WEEK_SECONDS
    beacons = await store.all_beacons(cog.bot.state, guild.id)
    weekly_beacons = [(thread_id, beacon) for thread_id, beacon in beacons if beacon["opened_at"] >= since]
    reps = await store.get_reps(cog.bot.state, guild.id)
    embed = build_digest_embed(compute_stats(weekly_beacons, reps), since)

    channel = guild.get_channel(digest_channel_id)
    if channel is None:
        logger.warning("Beacon digest channel %s is missing for guild %s", digest_channel_id, guild.id)
    else:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            logger.warning("Could not post beacon digest for guild %s", guild.id)

    config["last_digest_at"] = now
    await store.set_config(cog.bot.state, guild.id, config)
