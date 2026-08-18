"""Weekly 'This Week in Star Citizen' schedule: /twisc subscribe/unsubscribe/list/post."""

from __future__ import annotations

import logging
import re
import traceback
from dataclasses import dataclass

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot, handle_check_failure
from src.starcitizenwiki_api.comm_links import CommLink

logger = logging.getLogger(__name__)

_STATE_KEY = "twisc"
_COMM_LINK_TITLE = "This Week in Star Citizen"
POLL_INTERVAL = 1800  # seconds

SCHEDULE_TITLE = "The Weekly Community Content Schedule"

_DAY_HEADING = re.compile(r"^(?:MON|TUES|WEDNES|THURS|FRI|SATUR|SUN)DAY, [A-Z]+ \d{1,2}(?:, \d{4})?$")


@dataclass(frozen=True)
class ScheduleDay:
    heading: str
    items: tuple[str, ...]


def parse_schedule(content: str | None) -> list[ScheduleDay]:
    """Extract the weekly schedule from a comm-link's translation text.

    Day paragraphs look like ``TUESDAY, AUGUST 11, 2026`` immediately
    followed (no blank line) by that day's first item; each subsequent
    blank-line-separated single-line paragraph is another item for that
    day, however many there are. Parsing ends at the first paragraph
    whose first line is not a day heading and that has more than one
    line: this is the real shape of the community-manager sign-off in
    the observed comm-link text, e.g. ``Freyja Vanadis\\nSenior
    Community Manager`` as a single two-line paragraph. A sign-off
    rendered any other way (for example as two separate single-line
    paragraphs) is out of contract and not handled.
    Returns [] when the schedule marker is missing or the format has changed.
    """
    if not content or SCHEDULE_TITLE not in content:
        return []
    tail = content.split(SCHEDULE_TITLE, 1)[1]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", tail) if p.strip()]

    days: list[ScheduleDay] = []
    heading: str | None = None
    items: list[str] = []
    for paragraph in paragraphs:
        lines = paragraph.split("\n")
        if _DAY_HEADING.match(lines[0]) and len(lines) <= 2:
            if heading is not None:
                days.append(ScheduleDay(heading=heading, items=tuple(items)))
            heading = lines[0]
            items = lines[1:]
        elif len(lines) > 1 or heading is None:
            break
        else:
            items.append(paragraph)
    if heading is not None:
        days.append(ScheduleDay(heading=heading, items=tuple(items)))
    return days


_EMBED_COLOR = 0x0099D6


def build_schedule_embed(comm_link: CommLink, days: list[ScheduleDay]) -> discord.Embed:
    embed = discord.Embed(title=SCHEDULE_TITLE, url=comm_link.rsi_url, color=_EMBED_COLOR)
    for day in days:
        value = "\n".join(f"- {item}" for item in day.items) or "​"
        embed.add_field(name=day.heading.title(), value=value, inline=False)
    if comm_link.rsi_url:
        embed.set_footer(text=comm_link.rsi_url)
    return embed


class TwiscCog(commands.Cog):
    """Weekly community content schedule notifications."""

    twisc = app_commands.Group(name="twisc", description="This Week in Star Citizen schedule")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.subscriptions: list[dict] = []
        self.last_posted_id: int | None = None

    async def cog_load(self) -> None:
        data = await self.bot.state.get(_STATE_KEY) or {}
        self.subscriptions = data.get("subscriptions", [])
        self.last_posted_id = data.get("last_posted_id")
        self.poll_loop.start()

    async def cog_unload(self) -> None:
        self.poll_loop.cancel()

    async def _save(self) -> None:
        await self.bot.state.set(
            _STATE_KEY,
            {"subscriptions": self.subscriptions, "last_posted_id": self.last_posted_id},
        )

    @tasks.loop(seconds=POLL_INTERVAL)
    async def poll_loop(self) -> None:
        try:
            await self._check_latest()
        except Exception:
            logger.exception("TWISC poll loop failed to check for a new comm-link")

    @poll_loop.before_loop
    async def before_poll_loop(self) -> None:
        await self.bot.wait_until_ready()

    @poll_loop.error
    async def poll_loop_error(self, error: Exception) -> None:
        logger.exception("TWISC poll loop error: %s", error)

    async def _fetch_latest(self) -> CommLink | None:
        results = await self.bot.comm_links_api.search(_COMM_LINK_TITLE, limit=1)
        return next((r for r in results if r.title == _COMM_LINK_TITLE), None)

    async def _check_latest(self) -> None:
        if not self.subscriptions:
            return
        latest = await self._fetch_latest()
        if latest is None or latest.id is None:
            return
        if self.last_posted_id is None:
            # First run: record the current week so an old post is not replayed.
            self.last_posted_id = latest.id
            await self._save()
            return
        if latest.id <= self.last_posted_id:
            return

        days = parse_schedule(latest.content)
        if not days:
            logger.warning("Comm-link %s has no parseable schedule; skipping", latest.id)
            return

        embed = build_schedule_embed(latest, days)
        for sub in self.subscriptions:
            try:
                await self._post_to_channel(sub["discord_channel_id"], embed)
            except Exception:
                logger.exception("Failed to post schedule to channel %s", sub["discord_channel_id"])
        self.last_posted_id = latest.id
        await self._save()

    async def _post_to_channel(self, channel_id: int, embed: discord.Embed) -> None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.warning("TWISC channel %s is unavailable", channel_id)
                return
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("Failed to post schedule to channel %s: %s", channel_id, exc)

    async def _latest_embed(self) -> discord.Embed | None:
        latest = await self._fetch_latest()
        if latest is None:
            return None
        days = parse_schedule(latest.content)
        if not days:
            return None
        return build_schedule_embed(latest, days)

    @twisc.command(name="subscribe", description="Post the weekly schedule in this channel every week")
    @app_commands.check(admin_or_sc_bot)
    async def subscribe(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if any(s["discord_channel_id"] == interaction.channel_id for s in self.subscriptions):
            await interaction.followup.send("This channel is already subscribed.", ephemeral=True)
            return

        self.subscriptions.append({"discord_channel_id": interaction.channel_id, "guild_id": interaction.guild_id})
        await self._save()

        embed = await self._latest_embed()
        if embed is not None:
            await self._post_to_channel(interaction.channel_id, embed)
            note = "Here is the current week to start you off."
        else:
            note = "The current schedule could not be fetched; the next weekly post will appear here."
        await interaction.followup.send(f"✅ Subscribed to the weekly schedule. {note}", ephemeral=True)

    @twisc.command(name="unsubscribe", description="Stop posting the weekly schedule in this channel")
    @app_commands.check(admin_or_sc_bot)
    async def unsubscribe(self, interaction: discord.Interaction) -> None:
        match = next((s for s in self.subscriptions if s["discord_channel_id"] == interaction.channel_id), None)
        if match is None:
            await interaction.response.send_message("This channel is not subscribed.", ephemeral=True)
            return
        self.subscriptions.remove(match)
        await self._save()
        await interaction.response.send_message("Unsubscribed from the weekly schedule.", ephemeral=True)

    @twisc.command(name="list", description="List channels subscribed to the weekly schedule")
    async def list_subs(self, interaction: discord.Interaction) -> None:
        guild_subs = [s for s in self.subscriptions if s.get("guild_id") == interaction.guild_id]
        if not guild_subs:
            await interaction.response.send_message("No weekly schedule subscriptions in this server.", ephemeral=True)
            return
        lines = "\n".join(f"<#{s['discord_channel_id']}>" for s in guild_subs)
        embed = discord.Embed(title="Weekly Schedule Subscriptions", description=lines, color=_EMBED_COLOR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @twisc.command(name="post", description="Post the current weekly schedule in this channel")
    @app_commands.check(admin_or_sc_bot)
    async def post(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        embed = await self._latest_embed()
        if embed is None:
            await interaction.followup.send(
                "The current schedule could not be fetched or parsed. Try again later.", ephemeral=True
            )
            return
        await interaction.followup.send(embed=embed)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await handle_check_failure(interaction, error)
            return
        cmd = interaction.command.qualified_name if interaction.command else "unknown"
        logger.exception("Unhandled error in twisc command: %s", error)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await interaction.client.dm_owner(f"**Error in `/{cmd}`**\n```\n{tb[:1900]}\n```")
        msg = "Something went wrong. Check the bot logs for details."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TwiscCog(bot))
