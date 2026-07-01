"""The /lookup command: RSI citizen profile lookup."""

from __future__ import annotations

import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

RSI_BASE = "https://robertsspaceindustries.com"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = aiohttp.ClientTimeout(total=10)
_EMBED_COLOR = 0x1B4F8A


def _abs(path: str) -> str:
    return path if path.startswith("http") else RSI_BASE + path


def _strip(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _find(html: str, pattern: str, flags: int = re.DOTALL) -> str:
    m = re.search(pattern, html, flags)
    return m.group(1).strip() if m else ""


def _parse_profile(html: str) -> dict:
    record = _find(html, r'citizen-record[^>]*>.*?<strong class="value">(#\d+)</strong>')
    handle = _find(html, r'<span class="label">Handle name</span>\s*<strong class="value">([^<]+)</strong>')
    # Avatar is first <img> inside the profile thumb (before main-org section)
    profile_block = html[html.find('class="profile left-col"') : html.find('class="main-org')]
    avatar_path = _find(profile_block, r'<div class="thumb">\s*<img src="([^"]+)"')
    enlisted = _find(html, r'<span class="label">Enlisted</span>\s*<strong class="value">([^<]+)</strong>')
    location = _strip(_find(html, r'<span class="label">Location</span>\s*<strong class="value">(.*?)</strong>'))
    location = re.sub(r"\s*,\s*", ", ", location).strip(", ")
    fluency = _strip(_find(html, r'<span class="label">Fluency</span>\s*<strong class="value">(.*?)</strong>'))
    return {
        "handle": handle,
        "record": record,
        "avatar": _abs(avatar_path) if avatar_path else None,
        "enlisted": enlisted,
        "location": location,
        "fluency": fluency,
    }


def _parse_orgs(html: str) -> list[dict]:
    """Parse all orgs from the /organizations sub-page."""
    orgs = []
    # Each org has: <a href="/orgs/SID" class="value">Full Name</a>
    # followed by SID and rank entries
    for m in re.finditer(
        r'<a href="(/orgs/[^"]+)" class="value"[^>]*>([^<]+)</a>'
        r'.*?<span class="label">[^<]*SID[^<]*</span>\s*<strong class="value">([^<]+)</strong>'
        r'.*?<span class="label">[^<]*rank[^<]*</span>\s*<strong class="value">([^<]+)</strong>',
        html,
        re.DOTALL | re.IGNORECASE,
    ):
        orgs.append(
            {
                "url": RSI_BASE + m.group(1),
                "name": m.group(2).strip(),
                "sid": m.group(3).strip(),
                "rank": m.group(4).strip(),
            }
        )
    return orgs


def _build_embed(username: str, profile: dict, orgs: list[dict]) -> discord.Embed:
    profile_url = f"{RSI_BASE}/en/citizens/{username}"
    embed = discord.Embed(
        title=profile["handle"] or username,
        url=profile_url,
        color=_EMBED_COLOR,
    )

    if profile["avatar"]:
        embed.set_thumbnail(url=profile["avatar"])

    if profile["record"]:
        embed.add_field(name="Citizen Record", value=profile["record"], inline=True)
    if profile["enlisted"]:
        embed.add_field(name="Enlisted", value=profile["enlisted"], inline=True)
    if profile["location"]:
        embed.add_field(name="Location", value=profile["location"], inline=True)
    if profile["fluency"]:
        embed.add_field(name="Fluency", value=profile["fluency"], inline=True)

    if orgs:
        lines = [f"[{o['name']}]({o['url']}) — {o['rank']}" for o in orgs]
        embed.add_field(name="Organizations", value="\n".join(lines), inline=False)

    embed.set_footer(text="Source: robertsspaceindustries.com")
    return embed


class LookupCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT)
        return self._session

    async def cog_unload(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @app_commands.command(name="lookup", description="Look up a Star Citizen citizen profile")
    @app_commands.describe(username="RSI handle to look up")
    async def lookup(self, interaction: discord.Interaction, username: str) -> None:
        await interaction.response.defer()
        session = await self._get_session()
        profile_url = f"{RSI_BASE}/en/citizens/{username}"
        orgs_url = f"{RSI_BASE}/en/citizens/{username}/organizations"
        try:
            async with session.get(profile_url) as r:
                if r.status == 404:
                    await interaction.followup.send(f"No citizen found for **{username}**.", ephemeral=True)
                    return
                r.raise_for_status()
                profile_html = await r.text()
            async with session.get(orgs_url) as r:
                r.raise_for_status()
                orgs_html = await r.text()
        except aiohttp.ClientError as exc:
            await interaction.followup.send(f"Couldn't reach RSI: {exc}", ephemeral=True)
            return

        profile = _parse_profile(profile_html)
        if not profile["handle"]:
            await interaction.followup.send(f"Couldn't parse profile for **{username}**.", ephemeral=True)
            return

        orgs = _parse_orgs(orgs_html)
        await interaction.followup.send(embed=_build_embed(username, profile, orgs))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LookupCog(bot))
