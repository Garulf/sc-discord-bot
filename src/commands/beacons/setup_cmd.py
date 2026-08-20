"""Admin setup: install the panel and map category roles."""

from __future__ import annotations

import logging

import discord

from . import store
from .categories import CATEGORIES, short_label
from .embeds import build_panel_content

logger = logging.getLogger(__name__)

_STATUS_TAGS = ("open", "closed")
_MAX_FORUM_TAGS = 20


class _TagLimitExceeded(Exception):
    """Raised when a forum channel does not have room for the beacon tags."""


async def handle_setup(
    cog,
    interaction: discord.Interaction,
    channel: discord.TextChannel | discord.ForumChannel | None = None,
) -> None:
    await interaction.response.defer(ephemeral=True)
    target = channel or interaction.channel
    if isinstance(target, discord.Thread) and isinstance(target.parent, discord.ForumChannel):
        target = target.parent
    old = await store.get_config(cog.bot.state, interaction.guild.id)
    roles = old["roles"] if old else {}
    await cog.refresh_command_mentions()
    content = build_panel_content(cog.command_mention)
    try:
        if isinstance(target, discord.ForumChannel):
            tag_ids = await _ensure_tags(target)
            created = await target.create_thread(name="Open a beacon", content=content)
            await created.thread.edit(pinned=True)
            config = {
                "channel_id": target.id,
                "mode": "forum",
                "panel_message_id": created.thread.id,
                "tag_ids": tag_ids,
                "roles": roles,
            }
        elif isinstance(target, discord.TextChannel):
            message = await target.send(content)
            config = {
                "channel_id": target.id,
                "mode": "thread",
                "panel_message_id": message.id,
                "tag_ids": {},
                "roles": roles,
            }
        else:
            await interaction.followup.send(
                "Run this in a text channel or a forum channel, or pass one with the `channel` option.",
                ephemeral=True,
            )
            return
    except _TagLimitExceeded as error:
        await interaction.followup.send(str(error), ephemeral=True)
        return
    except discord.HTTPException as error:
        logger.exception("Beacon setup failed")
        await interaction.followup.send(
            f"Setup failed: {error}. Check the bot's permissions in this channel.", ephemeral=True
        )
        return
    if old:
        await _delete_old_panel(interaction.guild, old)
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    await interaction.followup.send("Beacon system installed.", ephemeral=True)


async def _delete_old_panel(guild: discord.Guild, old: dict) -> None:
    channel = guild.get_channel(old["channel_id"])
    if channel is None:
        return
    try:
        if old["mode"] == "forum":
            thread = channel.get_thread(old["panel_message_id"])
            if thread is not None:
                await thread.delete()
        else:
            await channel.get_partial_message(old["panel_message_id"]).delete()
    except discord.HTTPException:
        logger.warning("Could not delete the previous beacon panel %s", old["panel_message_id"])


async def _ensure_tags(channel: discord.ForumChannel) -> dict[str, int]:
    wanted = {key: short_label(CATEGORIES[key]) for key in CATEGORIES}
    wanted.update({key: key.capitalize() for key in _STATUS_TAGS})
    existing = {tag.name: tag for tag in channel.available_tags}
    missing = [discord.ForumTag(name=label) for label in wanted.values() if label not in existing]
    if missing:
        if len(channel.available_tags) + len(missing) > _MAX_FORUM_TAGS:
            free = _MAX_FORUM_TAGS - len(channel.available_tags)
            raise _TagLimitExceeded(
                f"This forum already has {len(channel.available_tags)} tags and only has room for "
                f"{max(free, 0)} more, but the beacon system needs {len(missing)} tag slots. "
                "Remove some existing tags and run setup again."
            )
        updated = await channel.edit(available_tags=[*channel.available_tags, *missing])
        channel = updated or channel
        existing = {tag.name: tag for tag in channel.available_tags}
    return {key: existing[label].id for key, label in wanted.items()}


async def handle_role(cog, interaction: discord.Interaction, category_key: str, role: discord.Role) -> None:
    config = await store.get_config(cog.bot.state, interaction.guild.id)
    if config is None:
        await interaction.response.send_message("Run `/beacon setup` first.", ephemeral=True)
        return
    config["roles"][category_key] = role.id
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    label = CATEGORIES[category_key].label
    await interaction.response.send_message(f"{label} beacons will now ping {role.mention}.", ephemeral=True)


async def handle_config(
    cog,
    interaction: discord.Interaction,
    *,
    idle_warn: int | None,
    idle_close: int | None,
    escalate: int | None,
    voice: bool | None,
    voice_category: discord.CategoryChannel | None = None,
    digest_channel: discord.TextChannel | None,
    clear_digest: bool | None,
    schedule_role: discord.Role | None = None,
    clear_schedule_role: bool | None = None,
) -> None:
    config = await store.get_config(cog.bot.state, interaction.guild.id)
    if config is None:
        await interaction.response.send_message("Run `/beacon setup` first.", ephemeral=True)
        return
    settings = dict(config.get("settings") or {})
    if idle_warn is not None:
        settings["idle_warn_minutes"] = idle_warn
    if idle_close is not None:
        settings["idle_close_minutes"] = idle_close
    if escalate is not None:
        settings["escalate_minutes"] = escalate
    if voice is not None:
        settings["voice"] = voice
    if voice_category is not None:
        settings["voice_category_id"] = voice_category.id
    if clear_digest:
        settings["digest_channel_id"] = None
    elif digest_channel is not None:
        settings["digest_channel_id"] = digest_channel.id
    if clear_schedule_role:
        settings["schedule_role_id"] = None
    elif schedule_role is not None:
        settings["schedule_role_id"] = schedule_role.id
    config["settings"] = settings
    await store.set_config(cog.bot.state, interaction.guild.id, config)
    effective = store.get_settings(config)
    digest_value = effective["digest_channel_id"]
    digest_line = f"<#{digest_value}>" if digest_value else "not set"
    voice_category_id = effective["voice_category_id"]
    voice_category_line = f"<#{voice_category_id}>" if voice_category_id else "same as beacon channel"
    schedule_role_id = effective["schedule_role_id"]
    schedule_role_line = f"<@&{schedule_role_id}>" if schedule_role_id else "everyone"
    lines = [
        f"Idle warn: {effective['idle_warn_minutes']} minutes",
        f"Idle close: {effective['idle_close_minutes']} minutes",
        f"Escalate: {effective['escalate_minutes']} minutes",
        f"Voice channels: {'on' if effective['voice'] else 'off'}",
        f"Voice category: {voice_category_line}",
        f"Digest channel: {digest_line}",
        f"Can schedule beacons: {schedule_role_line}",
    ]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)
