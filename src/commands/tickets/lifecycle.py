"""Ticket lifecycle operations: open, claim, unclaim, close."""

from __future__ import annotations

import asyncio
import logging
import time

import discord

from . import store
from .categories import CATEGORIES
from .embeds import build_ticket_embed, ticket_title
from .location import parse_location
from .rules import STATUS_CLAIMED, STATUS_CLOSED, STATUS_OPEN, can_claim, can_close, can_unclaim

logger = logging.getLogger(__name__)

_LOCATION_KEYS = {"location", "route_from", "route_to"}
_SC_BOT_ROLE = "sc-bot"

_locks: dict[str, asyncio.Lock] = {}


def _lock_for(key: str) -> asyncio.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def is_ticket_admin(interaction: discord.Interaction) -> bool:
    member = interaction.user
    if not isinstance(member, discord.Member):
        return False
    if member.guild_permissions.administrator:
        return True
    return any(role.name.lower() == _SC_BOT_ROLE for role in member.roles)


async def _reply(interaction: discord.Interaction, message: str) -> None:
    await interaction.followup.send(message, ephemeral=True)


async def open_ticket(cog, interaction: discord.Interaction, category_key: str, field_values: dict[str, str]) -> None:
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    category = CATEGORIES[category_key]

    for key, value in field_values.items():
        if key in _LOCATION_KEYS and parse_location(value) is None:
            await _reply(
                interaction,
                f"`{value}` is not a valid location. Use the form `system:planet:location`, "
                "for example `Stanton:Hurston:Lorville` (later parts optional).",
            )
            return

    config = await store.get_config(cog.bot.state, guild.id)
    if config is None:
        await _reply(interaction, "Tickets are not set up yet. Ask an admin to run `/ticket setup`.")
        return

    lock = _lock_for(f"open:{guild.id}:{interaction.user.id}:{category_key}")
    async with lock:
        existing = await store.get_open_ticket(cog.bot.state, guild.id, interaction.user.id, category_key)
        if existing is not None:
            await _reply(
                interaction,
                f"You already have an open {category.label} ticket: https://discord.com/channels/{guild.id}/{existing}",
            )
            return

        channel = guild.get_channel(config["channel_id"])
        if channel is None:
            await _reply(interaction, "The ticket channel is missing. Ask an admin to re-run `/ticket setup`.")
            return

        ticket = {
            "guild_id": guild.id,
            "category": category_key,
            "requester_id": interaction.user.id,
            "claimer_id": None,
            "status": STATUS_OPEN,
            "opened_at": time.time(),
            "closed_at": None,
            "closed_by_id": None,
            "fields": field_values,
        }
        name = ticket_title(category_key, interaction.user.display_name)
        content, dropped_role_note, role_dropped = _resolve_ping_content(guild, config, category_key, category)
        embed = build_ticket_embed(ticket)

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
                    view=cog.ticket_view,
                )
                thread = created.thread
            else:
                thread = await channel.create_thread(name=name, type=discord.ChannelType.public_thread)
                await thread.send(content=content, embed=embed, view=cog.ticket_view)
            if dropped_role_note:
                await thread.send(dropped_role_note)
            await thread.add_user(interaction.user)
        except discord.HTTPException as error:
            logger.exception("Failed to create ticket thread")
            await _reply(interaction, f"Could not create the ticket: {error}. Check the bot's channel permissions.")
            return

        if role_dropped:
            config["roles"].pop(category_key, None)
            await store.set_config(cog.bot.state, guild.id, config)
        await store.save_ticket(cog.bot.state, thread.id, ticket)
        await store.set_open_ticket(cog.bot.state, guild.id, interaction.user.id, category_key, thread.id)
        await _reply(interaction, f"Ticket opened: {thread.mention}")


def _resolve_ping_content(guild, config: dict, category_key: str, category) -> tuple[str, str | None, bool]:
    role_id = config["roles"].get(category_key)
    if not role_id:
        return "", None, False
    role = guild.get_role(role_id)
    if role is not None:
        return f"<@&{role_id}>", None, False
    note = (
        f"The responder role mapped to {category.label} no longer exists and was unmapped. "
        "An admin can re-map it with `/ticket role`."
    )
    return "", note, True


def _resolve_tag(channel: discord.ForumChannel, config: dict, tag_key: str):
    tag_id = config.get("tag_ids", {}).get(tag_key)
    return channel.get_tag(tag_id) if tag_id else None


async def _load_ticket(cog, interaction: discord.Interaction):
    ticket = await store.get_ticket(cog.bot.state, interaction.channel.id)
    if ticket is None:
        await _reply(interaction, "This ticket is no longer tracked (its record was removed).")
        await _disable_buttons(interaction)
    return ticket


async def _disable_buttons(interaction: discord.Interaction) -> None:
    view = discord.ui.View.from_message(interaction.message)
    for item in view.children:
        item.disabled = True
    try:
        await interaction.message.edit(view=view)
    except discord.HTTPException:
        logger.warning("Could not disable buttons on ticket message %s", interaction.channel.id)


async def _unclaim_ticket(cog, interaction: discord.Interaction, ticket: dict) -> None:
    if not can_unclaim(ticket, interaction.user.id):
        await _reply(interaction, "Only the current claimer can unclaim.")
        return
    ticket["status"] = STATUS_OPEN
    ticket["claimer_id"] = None
    await store.save_ticket(cog.bot.state, interaction.channel.id, ticket)
    await interaction.message.edit(embed=build_ticket_embed(ticket))
    await interaction.channel.send(f"{interaction.user.mention} unclaimed this ticket.")
    await _reply(interaction, "Ticket unclaimed.")


async def handle_claim(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with _lock_for(f"ticket:{interaction.channel.id}"):
        ticket = await _load_ticket(cog, interaction)
        if ticket is None:
            return
        if can_unclaim(ticket, interaction.user.id):
            await _unclaim_ticket(cog, interaction, ticket)
            return
        if not can_claim(ticket, interaction.user.id):
            await _reply(interaction, "You cannot claim this ticket.")
            return
        ticket["status"] = STATUS_CLAIMED
        ticket["claimer_id"] = interaction.user.id
        await store.save_ticket(cog.bot.state, interaction.channel.id, ticket)
        await interaction.message.edit(embed=build_ticket_embed(ticket))
        await interaction.channel.send(f"{interaction.user.mention} claimed this ticket.")
        await _reply(interaction, "Ticket claimed.")


async def handle_unclaim(cog, interaction: discord.Interaction, ticket: dict | None = None) -> None:
    if ticket is not None:
        await _unclaim_ticket(cog, interaction, ticket)
        return
    await interaction.response.defer(ephemeral=True)
    async with _lock_for(f"ticket:{interaction.channel.id}"):
        ticket = await _load_ticket(cog, interaction)
        if ticket is None:
            return
        await _unclaim_ticket(cog, interaction, ticket)


async def handle_close(cog, interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)
    async with _lock_for(f"ticket:{interaction.channel.id}"):
        ticket = await _load_ticket(cog, interaction)
        if ticket is None:
            return
        if not can_close(ticket, interaction.user.id, is_ticket_admin(interaction)):
            await _reply(interaction, "Only the requester, the claimer, or an admin can close this ticket.")
            return
        ticket["status"] = STATUS_CLOSED
        ticket["closed_at"] = time.time()
        ticket["closed_by_id"] = interaction.user.id
        await store.save_ticket(cog.bot.state, interaction.channel.id, ticket)
        await store.clear_open_ticket(cog.bot.state, ticket["guild_id"], ticket["requester_id"], ticket["category"])
        await interaction.message.edit(embed=build_ticket_embed(ticket))
        await interaction.channel.send(f"Ticket closed by {interaction.user.mention}.")
        await _disable_buttons(interaction)
        await _reply(interaction, "Ticket closed.")
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
        logger.exception("Failed to archive ticket thread %s", interaction.channel.id)
