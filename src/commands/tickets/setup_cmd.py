"""Admin setup: install the panel and map category roles."""

from __future__ import annotations

import logging

import discord

from . import store
from .categories import CATEGORIES
from .embeds import build_panel_embed

logger = logging.getLogger(__name__)

_STATUS_TAGS = ("open", "closed")


async def handle_setup(cog, interaction: discord.Interaction) -> None:
    channel = interaction.channel
    old = await store.get_config(cog.bot.state, interaction.guild.id)
    roles = old["roles"] if old else {}
    try:
        if isinstance(channel, discord.ForumChannel):
            tag_ids = await _ensure_tags(channel)
            created = await channel.create_thread(name="Open a ticket", embed=build_panel_embed(), view=cog.panel_view)
            await created.thread.edit(pinned=True)
            config = {
                "channel_id": channel.id,
                "mode": "forum",
                "panel_message_id": created.thread.id,
                "tag_ids": tag_ids,
                "roles": roles,
            }
        elif isinstance(channel, discord.TextChannel):
            message = await channel.send(embed=build_panel_embed(), view=cog.panel_view)
            config = {
                "channel_id": channel.id,
                "mode": "thread",
                "panel_message_id": message.id,
                "tag_ids": {},
                "roles": roles,
            }
        else:
            await interaction.response.send_message("Run this in a text channel or a forum channel.", ephemeral=True)
            return
    except discord.HTTPException as error:
        logger.exception("Ticket setup failed")
        await interaction.response.send_message(
            f"Setup failed: {error}. Check the bot's permissions in this channel.", ephemeral=True
        )
        return
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    await interaction.response.send_message("Ticket system installed in this channel.", ephemeral=True)


async def _ensure_tags(channel: discord.ForumChannel) -> dict[str, int]:
    wanted = {key: CATEGORIES[key].label for key in CATEGORIES}
    wanted.update({key: key.capitalize() for key in _STATUS_TAGS})
    existing = {tag.name: tag for tag in channel.available_tags}
    missing = [discord.ForumTag(name=label) for label in wanted.values() if label not in existing]
    if missing:
        channel = await channel.edit(available_tags=[*channel.available_tags, *missing])
        existing = {tag.name: tag for tag in channel.available_tags}
    return {key: existing[label].id for key, label in wanted.items()}


async def handle_role(cog, interaction: discord.Interaction, category_key: str, role: discord.Role) -> None:
    config = await store.get_config(cog.bot.state, interaction.guild.id)
    if config is None:
        await interaction.response.send_message("Run `/ticket setup` first.", ephemeral=True)
        return
    config["roles"][category_key] = role.id
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    label = CATEGORIES[category_key].label
    await interaction.response.send_message(f"{label} tickets will now ping {role.mention}.", ephemeral=True)
