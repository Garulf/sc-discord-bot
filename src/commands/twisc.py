"""Weekly 'This Week in Star Citizen' schedule: /twisc subscribe/unsubscribe/list/post."""

from __future__ import annotations

import re
from dataclasses import dataclass

import discord

from src.starcitizenwiki_api.comm_links import CommLink

SCHEDULE_TITLE = "The Weekly Community Content Schedule"

_DAY_HEADING = re.compile(r"^(?:MON|TUES|WEDNES|THURS|FRI|SATUR|SUN)DAY, [A-Z]+ \d{1,2}, \d{4}$")


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
