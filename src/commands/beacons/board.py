"""Live beacon status board: a single embed listing open beacons for a guild."""

from __future__ import annotations

import logging

import discord

from . import store
from .categories import CATEGORIES
from .rules import STATUS_ACTIVE

logger = logging.getLogger(__name__)


def _status_label(status: str) -> str:
    return "Active" if status == STATUS_ACTIVE else "Open"


def _opened_at(entry: tuple[int, dict]) -> float:
    return entry[1]["opened_at"]


def build_board_embed(entries: list[tuple[int, dict]]) -> discord.Embed:
    embed = discord.Embed(title="Beacon Board")
    if not entries:
        embed.description = "No open beacons."
        return embed
    active = sorted((e for e in entries if e[1]["status"] == STATUS_ACTIVE), key=_opened_at)
    open_ = sorted((e for e in entries if e[1]["status"] != STATUS_ACTIVE), key=_opened_at)
    lines = [
        f"{CATEGORIES[beacon['category']].emoji} <#{thread_id}> - {_status_label(beacon['status'])}"
        for thread_id, beacon in active + open_
    ]
    embed.description = "\n".join(lines)
    return embed


async def refresh_board(cog, guild) -> None:
    config = await store.get_config(cog.bot.state, guild.id)
    if not config or "board" not in config:
        return
    board_info = config["board"]
    channel = guild.get_channel(board_info["channel_id"])
    if channel is None:
        return
    entries = await store.open_beacons(cog.bot.state, guild.id)
    embed = build_board_embed(entries)
    try:
        await channel.get_partial_message(board_info["message_id"]).edit(embed=embed)
    except discord.NotFound:
        config.pop("board", None)
        await store.set_config(cog.bot.state, guild.id, config)
    except discord.HTTPException:
        logger.warning("Could not refresh beacon board for guild %s", guild.id)


async def _delete_board_message(guild, board_info: dict) -> None:
    channel = guild.get_channel(board_info["channel_id"])
    if channel is None:
        return
    try:
        await channel.get_partial_message(board_info["message_id"]).delete()
    except discord.HTTPException:
        logger.warning("Could not delete previous beacon board message %s", board_info["message_id"])


async def _install_board(cog, interaction: discord.Interaction, config: dict) -> None:
    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("Run this in a text channel.", ephemeral=True)
        return
    old_board = config.get("board")
    if old_board is not None:
        await _delete_board_message(interaction.guild, old_board)
    entries = await store.open_beacons(cog.bot.state, interaction.guild.id)
    message = await channel.send(embed=build_board_embed(entries))
    config["board"] = {"channel_id": channel.id, "message_id": message.id}
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    await interaction.response.send_message("Beacon board installed.", ephemeral=True)


async def _remove_board(cog, interaction: discord.Interaction, config: dict) -> None:
    board_info = config.get("board")
    if board_info is None:
        await interaction.response.send_message("No board is installed.", ephemeral=True)
        return
    await _delete_board_message(interaction.guild, board_info)
    config.pop("board", None)
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    await interaction.response.send_message("Beacon board removed.", ephemeral=True)


async def handle_board(cog, interaction: discord.Interaction, action: str) -> None:
    config = await store.get_config(cog.bot.state, interaction.guild.id)
    if config is None:
        await interaction.response.send_message("Run `/beacon setup` first.", ephemeral=True)
        return
    if action == "remove":
        await _remove_board(cog, interaction, config)
    else:
        await _install_board(cog, interaction, config)
