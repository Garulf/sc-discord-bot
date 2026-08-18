"""RSI devtracker notifications: /devtracker subscribe/unsubscribe/list."""

from __future__ import annotations

import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot, handle_check_failure
from src.rsi_devtracker import DevPost, DevTrackerClient

logger = logging.getLogger(__name__)

_STATE_KEY = "devtracker"
POLL_INTERVAL = 1800  # seconds
MAX_POSTS_PER_CYCLE = 10
_EMBED_COLOR = 0x0099D6


def build_devpost_embed(post: DevPost) -> discord.Embed:
    embed = discord.Embed(
        title=post.thread or "Dev Tracker Post",
        url=post.url,
        description=post.details,
        color=_EMBED_COLOR,
        timestamp=discord.utils.utcnow(),
    )
    embed.set_author(name=post.author, icon_url=post.avatar_url)
    if post.category:
        embed.set_footer(text=post.category)
    return embed


class DevTrackerCog(commands.Cog):
    """Posts new RSI devtracker entries to subscribed channels."""

    devtracker = app_commands.Group(name="devtracker", description="RSI dev tracker notifications")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.client = DevTrackerClient()
        self.subscriptions: list[dict] = []
        self.last_post_id: int | None = None

    async def cog_load(self) -> None:
        data = await self.bot.state.get(_STATE_KEY) or {}
        self.subscriptions = data.get("subscriptions", [])
        self.last_post_id = data.get("last_post_id")
        self.poll_loop.start()

    async def cog_unload(self) -> None:
        self.poll_loop.cancel()
        await self.client.close()

    async def _save(self) -> None:
        await self.bot.state.set(
            _STATE_KEY,
            {"subscriptions": self.subscriptions, "last_post_id": self.last_post_id},
        )

    @tasks.loop(seconds=POLL_INTERVAL)
    async def poll_loop(self) -> None:
        try:
            await self._check_latest()
        except Exception:  # noqa: BLE001 - a failed cycle must not stop the loop
            logger.exception("Devtracker poll cycle failed")

    @poll_loop.before_loop
    async def before_poll_loop(self) -> None:
        await self.bot.wait_until_ready()

    @poll_loop.error
    async def poll_loop_error(self, error: Exception) -> None:
        logger.exception("Devtracker poll loop error: %s", error)

    async def _check_latest(self) -> None:
        if not self.subscriptions:
            return
        posts = await self.client.fetch_posts()
        if not posts:
            logger.warning("Devtracker returned no parseable posts; skipping cycle")
            return
        newest_id = max(post.post_id for post in posts)
        if self.last_post_id is None:
            # First run: record the current newest post so history is not replayed.
            self.last_post_id = newest_id
            await self._save()
            return

        fresh = sorted((p for p in posts if p.post_id > self.last_post_id), key=lambda p: p.post_id)
        if not fresh:
            return
        if len(fresh) > MAX_POSTS_PER_CYCLE:
            logger.warning(
                "Devtracker backlog: dropping %d oldest of %d new posts",
                len(fresh) - MAX_POSTS_PER_CYCLE,
                len(fresh),
            )
            fresh = fresh[-MAX_POSTS_PER_CYCLE:]

        for post in fresh:
            embed = build_devpost_embed(post)
            for sub in self.subscriptions:
                try:
                    await self._post_to_channel(sub["discord_channel_id"], embed)
                except Exception:  # noqa: BLE001 - one bad channel must not block the rest
                    logger.exception("Failed posting devtracker entry to channel %s", sub["discord_channel_id"])
        self.last_post_id = newest_id
        await self._save()

    async def _post_to_channel(self, channel_id: int, embed: discord.Embed) -> None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.warning("Devtracker channel %s is unavailable", channel_id)
                return
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("Failed to post devtracker entry to channel %s: %s", channel_id, exc)

    @devtracker.command(name="subscribe", description="Post new RSI dev tracker entries in this channel")
    @app_commands.check(admin_or_sc_bot)
    async def subscribe(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if any(s["discord_channel_id"] == interaction.channel_id for s in self.subscriptions):
            await interaction.followup.send("This channel is already subscribed.", ephemeral=True)
            return

        self.subscriptions.append({"discord_channel_id": interaction.channel_id, "guild_id": interaction.guild_id})
        await self._save()

        posts = await self.client.fetch_posts()
        if posts:
            await interaction.followup.send(
                "✅ Subscribed to the RSI dev tracker. Latest post:",
                embed=build_devpost_embed(posts[0]),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "✅ Subscribed to the RSI dev tracker. New posts will appear here.",
                ephemeral=True,
            )

    @devtracker.command(name="unsubscribe", description="Stop posting dev tracker entries in this channel")
    @app_commands.check(admin_or_sc_bot)
    async def unsubscribe(self, interaction: discord.Interaction) -> None:
        match = next((s for s in self.subscriptions if s["discord_channel_id"] == interaction.channel_id), None)
        if match is None:
            await interaction.response.send_message("This channel is not subscribed.", ephemeral=True)
            return
        self.subscriptions.remove(match)
        await self._save()
        await interaction.response.send_message("Unsubscribed from the RSI dev tracker.", ephemeral=True)

    @devtracker.command(name="list", description="List channels subscribed to the dev tracker")
    async def list_subs(self, interaction: discord.Interaction) -> None:
        guild_subs = [s for s in self.subscriptions if s.get("guild_id") == interaction.guild_id]
        if not guild_subs:
            await interaction.response.send_message("No dev tracker subscriptions in this server.", ephemeral=True)
            return
        lines = "\n".join(f"<#{s['discord_channel_id']}>" for s in guild_subs)
        embed = discord.Embed(title="Dev Tracker Subscriptions", description=lines, color=_EMBED_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await handle_check_failure(interaction, error)
            return
        cmd = interaction.command.qualified_name if interaction.command else "unknown"
        logger.exception("Unhandled error in devtracker command: %s", error)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await interaction.client.dm_owner(f"**Error in `/{cmd}`**\n```\n{tb[:1900]}\n```")
        msg = "Something went wrong. Check the bot logs for details."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DevTrackerCog(bot))
