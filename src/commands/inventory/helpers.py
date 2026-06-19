"""Pure helpers and constants for the /inventory command group."""

from __future__ import annotations

ITEMS = [f"DCHS-{i:02d}" for i in range(1, 8)]
_STATE_KEY_PREFIX = "inventory"
MAX_EMBED_FIELDS = 25


def guild_key(guild_id: int) -> str:
    return f"{_STATE_KEY_PREFIX}:{guild_id}"


def complete_sets(inventory: dict[str, int]) -> int:
    """Minimum count across all 7 items — the number of complete sets."""
    return min(inventory.get(item, 0) for item in ITEMS)


def embed_color(inventory: dict[str, int]) -> int:
    if complete_sets(inventory) > 0:
        return 0x57F287  # green
    if any(inventory.values()):
        return 0x5865F2  # blurple
    return 0x99AAB5  # gray


def format_field(inventory: dict[str, int]) -> str:
    """Compact per-item lines for embed fields in the everyone view."""
    lines = []
    for item in ITEMS:
        count = inventory.get(item, 0)
        num = item.removeprefix("DCHS-")
        if count > 0:
            suffix = f" ×{count}" if count > 1 else ""
            lines.append(f"✅ {num}{suffix}")
        else:
            lines.append(f"❌ {num}")
    sets = complete_sets(inventory)
    lines.append(f"🏆 **{sets} set{'s' if sets != 1 else ''}**" if sets else "*no complete set*")
    return "\n".join(lines)


def format_mine(inventory: dict[str, int]) -> str:
    """Richer per-item lines for the personal mine view."""
    lines = []
    for item in ITEMS:
        count = inventory.get(item, 0)
        if count > 0:
            suffix = f" ×{count}" if count > 1 else ""
            lines.append(f"✅ **{item}**{suffix}")
        else:
            lines.append(f"❌ ~~{item}~~")
    return "\n".join(lines)
