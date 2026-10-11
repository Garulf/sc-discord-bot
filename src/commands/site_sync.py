"""Keep the Ghosts of Klescher site's member access in step with Discord roles.

Pushes role, nickname and membership changes in the GOK guild to the site's
bot API, plus a full roster resync on startup and every few hours. Loaded
only when GOK_SITE_URL, GOK_SITE_TOKEN and GOK_GUILD_ID are all set.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass

import discord
from discord.ext import commands, tasks

from src.gok_site import GokSiteClient, MemberPayload

logger = logging.getLogger(__name__)

RESYNC_HOURS = 6
# A full resync revokes everyone missing from the list, so refuse to send one
# built from a partially loaded member cache.
MIN_ROSTER_COVERAGE = 0.9


@dataclass(frozen=True)
class SiteSyncConfig:
    url: str
    token: str
    guild_id: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> SiteSyncConfig | None:
        url, token, guild_id = (env.get(name, "") for name in ("GOK_SITE_URL", "GOK_SITE_TOKEN", "GOK_GUILD_ID"))
        if not (url and token and guild_id):
            return None
        return cls(url=url, token=token, guild_id=int(guild_id))


def member_payload(member: discord.Member) -> MemberPayload:
    return {
        "id": str(member.id),
        "roles": [str(role.id) for role in member.roles if not role.is_default()],
        "name": member.display_name,
    }


class SiteSyncCog(commands.Cog):
    def __init__(self, bot: commands.Bot, client: GokSiteClient, guild_id: int) -> None:
        self.bot = bot
        self.client = client
        self.guild_id = guild_id

    async def cog_load(self) -> None:
        self.resync_loop.start()

    async def cog_unload(self) -> None:
        self.resync_loop.cancel()
        await self.client.close()

    @tasks.loop(hours=RESYNC_HOURS)
    async def resync_loop(self) -> None:
        await self.resync()

    @resync_loop.before_loop
    async def _wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()

    async def resync(self) -> None:
        guild = self.bot.get_guild(self.guild_id)
        if guild is None:
            logger.warning("Site resync skipped: bot is not in guild %s", self.guild_id)
            return
        if not guild.chunked:
            await guild.chunk()
        members = guild.members
        expected = guild.member_count or 0
        if len(members) < expected * MIN_ROSTER_COVERAGE:
            logger.warning("Site resync skipped: only %d of %d members loaded", len(members), expected)
            return
        try:
            updated = await self.client.sync_roster([member_payload(member) for member in members])
        except Exception:
            logger.exception("Site resync failed")
            return
        logger.info("Site resync sent %d members, %d site users changed", len(members), updated)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if after.guild.id != self.guild_id:
            return
        if before.roles == after.roles and before.display_name == after.display_name:
            return
        await self._push(after)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User) -> None:
        if before.display_name == after.display_name:
            return
        guild = self.bot.get_guild(self.guild_id)
        member = guild.get_member(after.id) if guild else None
        if member is not None:
            await self._push(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.guild.id != self.guild_id:
            return
        try:
            await self.client.remove_member(member.id)
        except Exception:
            logger.exception("Failed to revoke site access for %s", member.id)

    async def _push(self, member: discord.Member) -> None:
        try:
            await self.client.update_member(member_payload(member))
        except Exception:
            logger.exception("Failed to push %s to the site", member.id)


async def setup(bot: commands.Bot) -> None:
    config = SiteSyncConfig.from_env(os.environ)
    if config is None:
        logger.info("Site sync disabled: GOK_SITE_URL, GOK_SITE_TOKEN or GOK_GUILD_ID not set")
        return
    await bot.add_cog(SiteSyncCog(bot, GokSiteClient(config.url, config.token), config.guild_id))
