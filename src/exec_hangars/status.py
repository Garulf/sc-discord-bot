from datetime import datetime, timezone
from typing import Optional

from src.exec_hangars.constants import LIGHT_COUNT
from src.exec_hangars.schedule import HangarSchedule
from src.exec_hangars.states import HangarPhase, LightState

LIGHT_EMOJI = {
    LightState.GREEN: "🟩",
    LightState.RED: "🟥",
    LightState.EXPIRED: "⬛",
    LightState.ORANGE: "🟧",
}

PHASE_LABEL = {
    HangarPhase.CHARGING: "Closed",
    HangarPhase.ACTIVE: "Open",
    HangarPhase.RESET: "Resetting",
}

PHASE_COLOR = {
    HangarPhase.CHARGING: 0xE74C3C,
    HangarPhase.ACTIVE: 0x2ECC71,
    HangarPhase.RESET: 0xF39C12,
}


def discord_timestamp(moment: datetime, style: str = "R") -> str:
    """Render a Discord dynamic timestamp that ticks down in the client."""
    return f"<t:{int(moment.timestamp())}:{style}>"


def _format_time_of_day(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour}:{dt.strftime('%M')} {ampm}"


def format_relative_time(dt: datetime, now: datetime) -> str:
    """Format a datetime as a human-readable relative string (Discord-style)."""
    day_diff = (now.date() - dt.date()).days
    if day_diff == 0:
        return f"Today at {_format_time_of_day(dt)}"
    if day_diff == 1:
        return f"Yesterday at {_format_time_of_day(dt)}"
    if day_diff < 7:
        return f"{day_diff} days ago"
    if day_diff < 14:
        return "1 week ago"
    if day_diff < 30:
        return f"{day_diff // 7} weeks ago"
    if day_diff < 60:
        return "1 month ago"
    if day_diff < 365:
        return f"{day_diff // 30} months ago"
    years = day_diff // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def render_lights(hangar) -> str:
    return " ".join(LIGHT_EMOJI[light] for light in hangar.lights)


def build_status(schedule: HangarSchedule, now: Optional[datetime] = None) -> dict:
    """Compute the live status of the hangar as embed-ready, discord-free data."""
    now = now if now is not None else datetime.now(timezone.utc)
    hangar = schedule.snapshot(now)

    lines = [
        f"**State:** {PHASE_LABEL[hangar.phase]}",
        f"**Status:** {render_lights(hangar)}  ({hangar.green_lights}/{LIGHT_COUNT})",
    ]

    if hangar.phase is HangarPhase.ACTIVE:
        lines.append(f"**Closes:** {discord_timestamp(schedule.next_close(now))}")
    else:
        lines.append(f"**Opens:** {discord_timestamp(schedule.next_open(now))}")

    lines.append(f"**Next light change:** {discord_timestamp(schedule.next_change(now))}")

    return {
        "title": "Executive Hangar",
        "description": "\n".join(lines),
        "color": PHASE_COLOR[hangar.phase],
        "phase": hangar.phase,
    }
