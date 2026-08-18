"""Compute and render beacon statistics for a guild."""

from __future__ import annotations

from typing import Any

import discord

from . import store
from .categories import CATEGORIES
from .rules import STATUS_CLOSED

_TOP_N = 5


def _top(counts: dict[int, int]) -> list[tuple[int, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:_TOP_N]


def compute_stats(beacons: list[tuple[int, dict[str, Any]]], reps: dict[int, int]) -> dict[str, Any]:
    total = len(beacons)
    closed = sum(1 for _, beacon in beacons if beacon["status"] == STATUS_CLOSED)
    open_ = total - closed

    by_category: dict[str, int] = {}
    responder_counts: dict[int, int] = {}
    join_durations: list[float] = []

    for _, beacon in beacons:
        category = beacon["category"]
        by_category[category] = by_category.get(category, 0) + 1
        for member in beacon["members"]:
            responder_counts[member] = responder_counts.get(member, 0) + 1
        first_joined_at = beacon.get("first_joined_at")
        opened_at = beacon.get("opened_at")
        if first_joined_at is not None and opened_at is not None:
            join_durations.append(first_joined_at - opened_at)

    avg_first_join_seconds = sum(join_durations) / len(join_durations) if join_durations else None

    return {
        "total": total,
        "open": open_,
        "closed": closed,
        "by_category": by_category,
        "top_responders": _top(responder_counts),
        "top_commended": _top(reps),
        "avg_first_join_seconds": avg_first_join_seconds,
    }


def _category_label(key: str) -> str:
    category = CATEGORIES.get(key)
    return category.label if category else key


def _by_category_lines(by_category: dict[str, int]) -> str:
    if not by_category:
        return "No beacons yet"
    ordered = sorted(by_category.items(), key=lambda item: (-item[1], item[0]))
    return "\n".join(f"{_category_label(key)}: {count}" for key, count in ordered)


def _leaderboard_lines(entries: list[tuple[int, int]]) -> str:
    if not entries:
        return "No data yet"
    return "\n".join(f"<@{user_id}>: {count}" for user_id, count in entries)


def build_stats_embed(stats: dict[str, Any]) -> discord.Embed:
    embed = discord.Embed(title="Beacon Statistics", color=discord.Color.blurple())
    embed.add_field(
        name="Overview",
        value=f"Total: {stats['total']}\nOpen: {stats['open']}\nClosed: {stats['closed']}",
        inline=False,
    )
    embed.add_field(name="By Category", value=_by_category_lines(stats["by_category"]), inline=False)
    embed.add_field(name="Top Responders", value=_leaderboard_lines(stats["top_responders"]), inline=True)
    embed.add_field(name="Top Commended", value=_leaderboard_lines(stats["top_commended"]), inline=True)
    avg = stats["avg_first_join_seconds"]
    avg_text = "n/a" if avg is None else f"{avg / 60:.1f} minutes"
    embed.add_field(name="Avg. Time to First Response", value=avg_text, inline=False)
    return embed


async def handle_stats(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    beacons = await store.all_beacons(cog.bot.state, interaction.guild.id)
    reps = await store.get_reps(cog.bot.state, interaction.guild.id)
    embed = build_stats_embed(compute_stats(beacons, reps))
    await interaction.followup.send(embed=embed)
