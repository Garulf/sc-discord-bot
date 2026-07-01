"""Live stream notifications: /stream subscribe/unsubscribe/list."""

from __future__ import annotations

import logging
import os
import traceback

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot, handle_check_failure
from src.streaming import StreamInfo, TikTokClient, TwitchClient, YouTubeClient

logger = logging.getLogger(__name__)

_STATE_KEY = "streams"
POLL_INTERVAL = 120  # seconds

_PLATFORM_CHOICES = [
    app_commands.Choice(name="Twitch", value="twitch"),
    app_commands.Choice(name="YouTube", value="youtube"),
    app_commands.Choice(name="TikTok", value="tiktok"),
]
_PLATFORM_LABELS = {"twitch": "Twitch", "youtube": "YouTube", "tiktok": "TikTok"}
_PLATFORM_COLORS = {"twitch": 0x9B59B6, "youtube": 0xFF0000, "tiktok": 0x010101}
_PLATFORM_ICONS = {"twitch": "🟣", "youtube": "🔴", "tiktok": "⚫"}


def build_live_embed(stream: StreamInfo) -> discord.Embed:
    label = _PLATFORM_LABELS[stream.platform]
    embed = discord.Embed(
        title=f"🔴 {stream.channel_name} is LIVE on {label}!",
        description=stream.title or None,
        url=stream.stream_url,
        color=_PLATFORM_COLORS[stream.platform],
    )
    if stream.thumbnail_url:
        embed.set_image(url=stream.thumbnail_url)
    if stream.game_or_category:
        embed.add_field(name="Playing", value=stream.game_or_category, inline=True)
    if stream.viewer_count is not None:
        embed.add_field(name="Viewers", value=f"{stream.viewer_count:,}", inline=True)
    return embed


class StreamCog(commands.Cog):
    """Live stream notifications for Twitch, YouTube, and TikTok."""

    stream = app_commands.Group(name="stream", description="Live stream notifications")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.subscriptions: list[dict] = []
        self.twitch = TwitchClient(
            client_id=os.getenv("TWITCH_CLIENT_ID", ""),
            client_secret=os.getenv("TWITCH_CLIENT_SECRET", ""),
        )
        self.youtube = YouTubeClient(api_key=os.getenv("YOUTUBE_API_KEY", ""))
        self.tiktok = TikTokClient()

    async def cog_load(self) -> None:
        data = await self.bot.state.get(_STATE_KEY) or {}
        self.subscriptions = data.get("subscriptions", [])
        self.poll_loop.start()

    async def cog_unload(self) -> None:
        self.poll_loop.cancel()
        await self.twitch.close()
        await self.youtube.close()
        await self.tiktok.close()

    async def _save(self) -> None:
        await self.bot.state.set(_STATE_KEY, {"subscriptions": self.subscriptions})

    @tasks.loop(seconds=POLL_INTERVAL)
    async def poll_loop(self) -> None:
        await self._check_all()

    @poll_loop.before_loop
    async def before_poll_loop(self) -> None:
        await self.bot.wait_until_ready()

    @poll_loop.error
    async def poll_loop_error(self, error: Exception) -> None:
        logger.exception("Stream poll loop error: %s", error)

    async def _check_all(self) -> None:
        if not self.subscriptions:
            return
        changed = False
        for sub in self.subscriptions:
            try:
                changed |= await self._check_sub(sub)
            except Exception:  # noqa: BLE001
                logger.exception("Error checking stream subscription %s", sub)
        if changed:
            await self._save()

    async def _check_sub(self, sub: dict) -> bool:
        platform = sub["platform"]
        login = sub["channel_login"]
        display = sub.get("channel_display", login)
        live_id = sub.get("live_id")

        if platform == "twitch":
            stream = await self.twitch.get_stream(login)
        elif platform == "youtube":
            stream = await self.youtube.get_stream(login, display, live_id)
        else:
            stream = await self.tiktok.get_stream(login)

        channel = self.bot.get_channel(sub["discord_channel_id"])
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(sub["discord_channel_id"])
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return False

        if stream and stream.stream_id != live_id:
            # New stream started (or first detection)
            # Backfill display name if it was stored as a raw channel ID
            if sub.get("channel_display") == sub.get("channel_login") and stream.channel_name:
                sub["channel_display"] = stream.channel_name
            try:
                msg = await channel.send(embed=build_live_embed(stream))
                sub["live_id"] = stream.stream_id
                sub["notification_message_id"] = msg.id
                logger.info("Posted live notification for %s/%s (stream %s)", platform, login, stream.stream_id)
                return True
            except (discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("Failed to post live notification: %s", exc)

        elif not stream and live_id:
            # Stream ended — leave the notification message in the channel
            sub["live_id"] = None
            sub["notification_message_id"] = None
            logger.info("Stream ended for %s/%s", platform, login)
            return True

        return False

    async def _delete_notif(self, sub: dict) -> None:
        mid = sub.get("notification_message_id")
        if not mid:
            return
        ch = self.bot.get_channel(sub["discord_channel_id"])
        if ch:
            try:
                msg = await ch.fetch_message(mid)
                await msg.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

    @stream.command(name="subscribe", description="Subscribe this channel to live stream notifications")
    @app_commands.describe(
        platform="Streaming platform",
        channel="Username or channel ID (YouTube: handle without @, or UCxxxx channel ID)",
    )
    @app_commands.choices(platform=_PLATFORM_CHOICES)
    @app_commands.check(admin_or_sc_bot)
    async def subscribe(
        self,
        interaction: discord.Interaction,
        platform: app_commands.Choice[str],
        channel: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        plat = platform.value
        login = channel.strip()

        # Validate + resolve display name
        if plat == "twitch":
            if not self.twitch._configured:
                await interaction.followup.send(
                    "Twitch credentials not configured. Set `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` in `.env`.",
                    ephemeral=True,
                )
                return
            display = await self.twitch.verify_user(login)
            if display is None:
                await interaction.followup.send(f"Twitch user **{login}** not found.", ephemeral=True)
                return
            login = login.lower()

        elif plat == "youtube":
            if not self.youtube._configured:
                await interaction.followup.send(
                    "YouTube API key not configured. Set `YOUTUBE_API_KEY` in `.env`.",
                    ephemeral=True,
                )
                return
            result = await self.youtube.resolve_channel(login)
            if result is None:
                await interaction.followup.send(
                    f"YouTube channel **{login}** not found. Try the handle without `@`, or paste the `UCxxxx` channel ID.",
                    ephemeral=True,
                )
                return
            login, display = result  # channel_id, display_name

        else:  # tiktok
            display = login.lstrip("@")
            login = display

        # Check for duplicate
        if any(
            s["platform"] == plat and s["channel_login"] == login and s["discord_channel_id"] == interaction.channel_id
            for s in self.subscriptions
        ):
            await interaction.followup.send(
                f"Already subscribed to **{display}** on {_PLATFORM_LABELS[plat]} in this channel.",
                ephemeral=True,
            )
            return

        self.subscriptions.append(
            {
                "platform": plat,
                "channel_login": login,
                "channel_display": display,
                "discord_channel_id": interaction.channel_id,
                "guild_id": interaction.guild_id,
                "live_id": None,
                "notification_message_id": None,
            }
        )
        await self._save()
        label = _PLATFORM_LABELS[plat]
        await interaction.followup.send(
            f"✅ Subscribed to **{display}** on {label}. Live notifications will appear here.",
            ephemeral=True,
        )

    @stream.command(name="unsubscribe", description="Remove a live stream notification subscription from this channel")
    @app_commands.describe(platform="Streaming platform", channel="Username to unsubscribe")
    @app_commands.choices(platform=_PLATFORM_CHOICES)
    @app_commands.check(admin_or_sc_bot)
    async def unsubscribe(
        self,
        interaction: discord.Interaction,
        platform: app_commands.Choice[str],
        channel: str,
    ) -> None:
        plat = platform.value
        login = channel.strip().lstrip("@").lower()

        match = next(
            (
                s
                for s in self.subscriptions
                if s["platform"] == plat
                and (s["channel_login"].lower() == login or s.get("channel_display", "").lower() == login)
                and s["guild_id"] == interaction.guild_id
            ),
            None,
        )
        if match is None:
            await interaction.response.send_message(
                f"No subscription found for **{channel}** on {_PLATFORM_LABELS[plat]} in this server.",
                ephemeral=True,
            )
            return

        await self._delete_notif(match)
        self.subscriptions.remove(match)
        await self._save()
        display = match.get("channel_display", channel)
        await interaction.response.send_message(
            f"Unsubscribed from **{display}** on {_PLATFORM_LABELS[plat]}.",
            ephemeral=True,
        )

    @stream.command(name="list", description="List live stream subscriptions in this server")
    async def list_subs(self, interaction: discord.Interaction) -> None:
        guild_subs = [s for s in self.subscriptions if s.get("guild_id") == interaction.guild_id]
        if not guild_subs:
            await interaction.response.send_message("No live stream subscriptions in this server.", ephemeral=True)
            return

        embed = discord.Embed(title="Live Stream Subscriptions", color=0x5865F2)
        by_platform: dict[str, list[str]] = {}
        for s in guild_subs:
            plat = s["platform"]
            ch_mention = f"<#{s['discord_channel_id']}>"
            name = s.get("channel_display", s["channel_login"])
            by_platform.setdefault(plat, []).append(f"**{name}** → {ch_mention}")

        for plat, lines in by_platform.items():
            icon = _PLATFORM_ICONS[plat]
            embed.add_field(name=f"{icon} {_PLATFORM_LABELS[plat]}", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await handle_check_failure(interaction, error)
            return
        cmd = interaction.command.qualified_name if interaction.command else "unknown"
        logger.exception("Unhandled error in stream command: %s", error)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await interaction.client.dm_owner(f"**Error in `/{cmd}`**\n```\n{tb[:1900]}\n```")
        msg = "Something went wrong. Check the bot logs for details."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StreamCog(bot))
