"""Beacon lifecycle operations: open, claim, unclaim, close."""

from __future__ import annotations

import asyncio
import logging
import time

import discord

from . import store
from .categories import CATEGORIES
from .embeds import beacon_title, build_beacon_embed
from .location import parse_location
from .rules import STATUS_ACTIVE, STATUS_CLOSED, STATUS_OPEN, can_close, can_join, can_leave

logger = logging.getLogger(__name__)

_LOCATION_KINDS = {"location", "route"}
_SC_BOT_ROLE = "sc-bot"

_locks: dict[str, asyncio.Lock] = {}


def _lock_for(key: str) -> asyncio.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def _field_kinds(category) -> dict[str, str]:
    return {spec.key: spec.kind for spec in category.fields}


def is_beacon_admin(interaction: discord.Interaction) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True
    return any(role.name.lower() == _SC_BOT_ROLE for role in member.roles)


async def _reply(interaction: discord.Interaction, message: str) -> None:
    await interaction.followup.send(message, ephemeral=True)


async def open_beacon(cog, interaction: discord.Interaction, category_key: str, field_values: dict[str, str]) -> None:
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

    lock = _lock_for(f"open:{guild.id}:{interaction.user.id}:{category_key}")
    async with lock:
        existing = await store.get_open_beacon(cog.bot.state, guild.id, interaction.user.id, category_key)
        if existing is not None:
            await _reply(
                interaction,
                f"You already have an open {category.label} beacon: https://discord.com/channels/{guild.id}/{existing}",
            )
            return

        channel = guild.get_channel(config["channel_id"])
        if channel is None:
            await _reply(interaction, "The beacon channel is missing. Ask an admin to re-run `/beacon setup`.")
            return

        beacon = {
            "guild_id": guild.id,
            "category": category_key,
            "requester_id": interaction.user.id,
            "members": [],
            "status": STATUS_OPEN,
            "opened_at": time.time(),
            "closed_at": None,
            "closed_by_id": None,
            "fields": field_values,
        }
        name = beacon_title(category_key, interaction.user.display_name)
        content, dropped_role_note, role_dropped = _resolve_ping_content(guild, config, category_key, category)
        embed = build_beacon_embed(beacon)

        try:
            if config["mode"] == "forum":
                tags = [
                    tag
                    for tag_key in (category_key, "open")
                    if (tag := _resolve_tag(channel, config, tag_key)) is not None
                ]
                created = await channel.create_thread(
                    name=name,
                    content=content or None,
                    embed=embed,
                    applied_tags=tags,
                    view=cog.beacon_view,
                )
                thread = created.thread
            else:
                thread = await channel.create_thread(name=name, type=discord.ChannelType.public_thread)
                await thread.send(content=content, embed=embed, view=cog.beacon_view)
            if dropped_role_note:
                await thread.send(dropped_role_note)
            await thread.add_user(interaction.user)
        except discord.HTTPException as error:
            logger.exception("Failed to create beacon thread")
            await _reply(interaction, f"Could not create the beacon: {error}. Check the bot's channel permissions.")
            return

        if role_dropped:
            config["roles"].pop(category_key, None)
            await store.set_config(cog.bot.state, guild.id, config)
        await store.save_beacon(cog.bot.state, thread.id, beacon)
        await store.set_open_beacon(cog.bot.state, guild.id, interaction.user.id, category_key, thread.id)
        await _reply(interaction, f"Beacon opened: {thread.mention}")


def _resolve_ping_content(guild, config: dict, category_key: str, category) -> tuple[str, str | None, bool]:
    role_id = config["roles"].get(category_key)
    if not role_id:
        return "", None, False
    role = guild.get_role(role_id)
    if role is not None:
        return f"<@&{role_id}>", None, False
    note = (
        f"The responder role mapped to {category.label} no longer exists and was unmapped. "
        "An admin can re-map it with `/beacon role`."
    )
    return "", note, True


def _resolve_tag(channel: discord.ForumChannel, config: dict, tag_key: str):
    tag_id = config.get("tag_ids", {}).get(tag_key)
    return channel.get_tag(tag_id) if tag_id else None


async def _load_beacon(cog, interaction: discord.Interaction):
    beacon = await store.get_beacon(cog.bot.state, interaction.channel.id)
    if beacon is None:
        await _reply(interaction, "This beacon is no longer tracked (its record was removed).")
        await _disable_buttons(interaction)
    return beacon


async def _disable_buttons(interaction: discord.Interaction) -> None:
    view = discord.ui.View.from_message(interaction.message)
    for item in view.children:
        item.disabled = True
    try:
        await interaction.message.edit(view=view)
    except discord.HTTPException:
        logger.warning("Could not disable buttons on beacon message %s", interaction.channel.id)


async def _leave_beacon(cog, interaction: discord.Interaction, beacon: dict) -> None:
    beacon["members"].remove(interaction.user.id)
    beacon["status"] = STATUS_ACTIVE if beacon["members"] else STATUS_OPEN
    await store.save_beacon(cog.bot.state, interaction.channel.id, beacon)
    try:
        await interaction.channel.remove_user(interaction.user)
    except discord.HTTPException:
        logger.warning("Could not remove %s from beacon thread %s", interaction.user.id, interaction.channel.id)
    await interaction.message.edit(embed=build_beacon_embed(beacon))
    await interaction.channel.send(f"{interaction.user.mention} left this beacon.")
    await _reply(interaction, "You left the beacon.")


async def handle_join(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with _lock_for(f"beacon:{interaction.channel.id}"):
        beacon = await _load_beacon(cog, interaction)
        if beacon is None:
            return
        if can_leave(beacon, interaction.user.id):
            await _leave_beacon(cog, interaction, beacon)
            return
        if not can_join(beacon, interaction.user.id):
            await _reply(interaction, "You cannot join this beacon.")
            return
        beacon["members"].append(interaction.user.id)
        beacon["status"] = STATUS_ACTIVE
        await store.save_beacon(cog.bot.state, interaction.channel.id, beacon)
        try:
            await interaction.channel.add_user(interaction.user)
        except discord.HTTPException:
            logger.warning("Could not add %s to beacon thread %s", interaction.user.id, interaction.channel.id)
        await interaction.message.edit(embed=build_beacon_embed(beacon))
        await interaction.channel.send(f"{interaction.user.mention} joined this beacon.")
        await _reply(interaction, "You joined the beacon.")


async def handle_close(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with _lock_for(f"beacon:{interaction.channel.id}"):
        beacon = await _load_beacon(cog, interaction)
        if beacon is None:
            return
        if not can_close(beacon, interaction.user.id, is_beacon_admin(interaction)):
            await _reply(interaction, "Only the requester, the claimer, or an admin can close this beacon.")
            return
        beacon["status"] = STATUS_CLOSED
        beacon["closed_at"] = time.time()
        beacon["closed_by_id"] = interaction.user.id
        await store.save_beacon(cog.bot.state, interaction.channel.id, beacon)
        await store.clear_open_beacon(cog.bot.state, beacon["guild_id"], beacon["requester_id"], beacon["category"])
        await interaction.message.edit(embed=build_beacon_embed(beacon))
        await interaction.channel.send(f"Beacon closed by {interaction.user.mention}.")
        await _disable_buttons(interaction)
        await _reply(interaction, "Beacon closed.")
        await _archive_channel(cog, interaction)


async def _archive_channel(cog, interaction: discord.Interaction) -> None:
    config = await store.get_config(cog.bot.state, interaction.guild.id)
    try:
        if config and config["mode"] == "forum":
            parent = interaction.channel.parent
            open_tag = _resolve_tag(parent, config, "open")
            closed_tag = _resolve_tag(parent, config, "closed")
            tags = [tag for tag in interaction.channel.applied_tags if tag != open_tag]
            if closed_tag is not None:
                tags.append(closed_tag)
            await interaction.channel.edit(applied_tags=tags, archived=True, locked=True)
        else:
            await interaction.channel.edit(archived=True)
    except discord.HTTPException:
        logger.exception("Failed to archive beacon thread %s", interaction.channel.id)
