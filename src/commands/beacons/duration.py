"""Relative duration parsing for scheduled beacons, e.g. "45m", "2h", "1h30m"."""

from __future__ import annotations

import re

MIN_SECONDS = 5 * 60
MAX_SECONDS = 24 * 60 * 60

_PATTERN = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?$")


def parse_duration(text: str) -> int | None:
    """Parse a relative duration like "1h30m" into seconds.

    Returns None if the text does not parse or the total falls outside
    [MIN_SECONDS, MAX_SECONDS].
    """
    if not text:
        return None
    match = _PATTERN.match(text.strip().lower().replace(" ", ""))
    if not match or not any(match.groups()):
        return None
    days, hours, minutes = (int(group) if group else 0 for group in match.groups())
    total = days * 86400 + hours * 3600 + minutes * 60
    if total < MIN_SECONDS or total > MAX_SECONDS:
        return None
    return total
