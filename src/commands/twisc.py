"""Weekly 'This Week in Star Citizen' schedule: /twisc subscribe/unsubscribe/list/post."""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    day. Parsing ends at the community-manager sign-off, which renders
    either as one two-line paragraph (name, then title) or as two
    consecutive single-line paragraphs. A single-line paragraph is only
    accepted as an item when it is NOT immediately followed by another
    single-line, non-heading paragraph; two such paragraphs in a row are
    treated as the sign-off's name and title, and everything from the
    first of the pair onward is dropped. (A day whose final two items are
    both standalone single-line paragraphs with nothing after them, i.e.
    no sign-off at all in the text, is misparsed by this rule; that shape
    does not occur in real comm-link content.)
    Returns [] when the schedule marker is missing or the format has changed.
    """
    if not content or SCHEDULE_TITLE not in content:
        return []
    tail = content.split(SCHEDULE_TITLE, 1)[1]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", tail) if p.strip()]

    days: list[ScheduleDay] = []
    heading: str | None = None
    items: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        lines = paragraph.split("\n")
        if _DAY_HEADING.match(lines[0]) and len(lines) <= 2:
            if heading is not None:
                days.append(ScheduleDay(heading=heading, items=tuple(items)))
            heading = lines[0]
            items = lines[1:]
            continue
        if len(lines) > 1 or heading is None:
            break
        next_paragraph = paragraphs[index + 1] if index + 1 < len(paragraphs) else None
        next_lines = next_paragraph.split("\n") if next_paragraph is not None else None
        next_is_signoff_partner = (
            next_lines is not None
            and len(next_lines) == 1
            and not _DAY_HEADING.match(next_lines[0])
        )
        if next_is_signoff_partner:
            break
        items.append(paragraph)
    if heading is not None:
        days.append(ScheduleDay(heading=heading, items=tuple(items)))
    return days
