"""Scheduled beacons: an RSVP embed posted ahead of time that opens the real
beacon thread automatically when its scheduled time arrives."""

from __future__ import annotations

import logging
import time

import discord

from . import lifecycle, store
from .categories import CATEGORIES
from .duration import MAX_SECONDS, MIN_SECONDS, parse_duration
from .embeds import build_scheduled_embed
from .lifecycle import is_beacon_admin, lock_for
from .location import parse_location

logger = logging.getLogger(__name__)

_LOCATION_KINDS = {"location", "route"}


def _field_kinds(category) -> dict[str, str]:
    return {spec.key: spec.kind for spec in category.fields}


def can_schedule(interaction: discord.Interaction, config: dict) -> bool:
    role_id = store.get_settings(config)["schedule_role_id"]
    if role_id is None:
        return True
    if getattr(interaction.user.guild_permissions, "administrator", False):
        return True
    return any(role.id == role_id for role in interaction.user.roles)


async def _reply(interaction: discord.Interaction, message: str) -> None:
    await interaction.followup.send(message, ephemeral=True)


async def open_or_schedule(
    cog, interaction: discord.Interaction, category_key: str, field_values: dict[str, str], when: str | None
) -> None:
    if when is None:
        await lifecycle.open_beacon(cog, interaction, category_key, field_values)
        return
    seconds = parse_duration(when)
    if seconds is None:
        await interaction.response.send_message(
            f"`{when}` is not a valid duration. Use a combination like `45m`, `2h`, or `1d`, "
            f"between {MIN_SECONDS // 60} minutes and {MAX_SECONDS // 3600} hours.",
            ephemeral=True,
        )
        return
    await schedule_beacon(cog, interaction, category_key, field_values, seconds)


async def schedule_beacon(
    cog, interaction: discord.Interaction, category_key: str, field_values: dict[str, str], when_seconds: int
) -> None:
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    category = CATEGORIES[category_key]

    kinds = _field_kinds(category)
    for key, value in field_values.items():
        if kinds.get(key) in _LOCATION_KINDS and parse_location(value) is None:
            await _reply(
                interaction,
                f"`{value}` is not a valid location. Use the form `system:planet:location`, "
                "for example `Stanton:Hurston:Lorville` (later parts optional).",
            )
            return

    config = await store.get_config(cog.bot.state, guild.id)
    if config is None:
        await _reply(interaction, "Beacons are not set up yet. Ask an admin to run `/beacon setup`.")
        return

    if not can_schedule(interaction, config):
        role_id = store.get_settings(config)["schedule_role_id"]
        role = guild.get_role(role_id)
        name = role.mention if role else "the configured role"
        await _reply(interaction, f"Only {name} can schedule a beacon.")
        return

    lock = lock_for(f"schedule_open:{guild.id}:{interaction.user.id}:{category_key}")
    async with lock:
        existing = await store.get_scheduled_open(cog.bot.state, guild.id, interaction.user.id, category_key)
        if existing is not None:
            await _reply(interaction, "You already have a pending scheduled beacon in this category.")
            return

        channel = guild.get_channel(config["channel_id"])
        if channel is None:
            await _reply(interaction, "The beacon channel is missing. Ask an admin to re-run `/beacon setup`.")
            return

        now = time.time()
        scheduled = {
            "guild_id": guild.id,
            "channel_id": channel.id,
            "category": category_key,
            "requester_id": interaction.user.id,
            "fields": field_values,
            "open_at": now + when_seconds,
            "rsvp": [],
            "reminded_at": None,
            "created_at": now,
        }
        embed = build_scheduled_embed(scheduled)
        try:
            message = await channel.send(embed=embed, view=cog.scheduled_beacon_view)
        except discord.HTTPException as error:
            logger.exception("Failed to post scheduled beacon")
            await _reply(interaction, f"Could not schedule the beacon: {error}. Check the bot's channel permissions.")
            return

        await store.save_scheduled(cog.bot.state, message.id, scheduled)
        await store.set_scheduled_open(cog.bot.state, guild.id, interaction.user.id, category_key, message.id)
        await _reply(interaction, f"Beacon scheduled: {message.jump_url}")


async def _load_scheduled(cog, interaction: discord.Interaction) -> dict | None:
    record = await store.get_scheduled(cog.bot.state, interaction.message.id)
    if record is None:
        await _reply(interaction, "This scheduled beacon is no longer tracked.")
        await _disable_view(interaction.message)
    return record


def _disabled_view(message) -> discord.ui.View:
    view = discord.ui.View.from_message(message)
    for item in view.children:
        item.disabled = True
    return view


async def _disable_view(message) -> None:
    try:
        await message.edit(view=_disabled_view(message))
    except discord.HTTPException:
        logger.warning("Could not disable buttons on scheduled beacon message %s", message.id)


async def handle_scheduled_join(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with lock_for(f"scheduled:{interaction.message.id}"):
        record = await _load_scheduled(cog, interaction)
        if record is None:
            return
        if interaction.user.id in record["rsvp"]:
            await _reply(interaction, "You are already RSVP'd. Use Leave to back out.")
            return
        record["rsvp"].append(interaction.user.id)
        await store.save_scheduled(cog.bot.state, interaction.message.id, record)
        await interaction.message.edit(embed=build_scheduled_embed(record))
        await _reply(interaction, "You're on the list.")


async def handle_scheduled_leave(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with lock_for(f"scheduled:{interaction.message.id}"):
        record = await _load_scheduled(cog, interaction)
        if record is None:
            return
        if interaction.user.id not in record["rsvp"]:
            await _reply(interaction, "You are not RSVP'd to this beacon.")
            return
        record["rsvp"].remove(interaction.user.id)
        await store.save_scheduled(cog.bot.state, interaction.message.id, record)
        await interaction.message.edit(embed=build_scheduled_embed(record))
        await _reply(interaction, "You're off the list.")


async def handle_scheduled_cancel(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with lock_for(f"scheduled:{interaction.message.id}"):
        record = await _load_scheduled(cog, interaction)
        if record is None:
            return
        if interaction.user.id != record["requester_id"] and not is_beacon_admin(interaction):
            await _reply(interaction, "Only the requester or an admin can cancel this scheduled beacon.")
            return
        await store.delete_scheduled(cog.bot.state, interaction.message.id)
        await store.clear_scheduled_open(cog.bot.state, record["guild_id"], record["requester_id"], record["category"])
        embed = build_scheduled_embed(record, cancelled_by_id=interaction.user.id)
        try:
            await interaction.message.edit(embed=embed, view=_disabled_view(interaction.message))
        except discord.HTTPException:
            logger.warning("Could not update scheduled beacon message %s after cancel", interaction.message.id)
        await _reply(interaction, "Scheduled beacon cancelled.")
