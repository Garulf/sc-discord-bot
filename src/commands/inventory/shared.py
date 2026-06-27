"""Shared code for the /inventory command group.

Contains constants, pure helpers, embed formatting, and guild-state accessors
used by all inventory subcommands.
"""

from __future__ import annotations

from collections.abc import Callable

from discord import app_commands

ITEMS = [f"DCHS-{i:02d}" for i in range(1, 8)]
_STATE_KEY_PREFIX = "inventory"
MAX_EMBED_FIELDS = 25


def guild_key(guild_id: int) -> str:
    return f"{_STATE_KEY_PREFIX}:{guild_id}"


def item_choices(current: str) -> list[app_commands.Choice[str]]:
    needle = current.strip().lower()
    return [app_commands.Choice(name=item, value=item) for item in ITEMS if not needle or needle in item.lower()]


def complete_sets(inventory: dict[str, int]) -> int:
    return min(inventory.get(item, 0) for item in ITEMS)


def embed_color(inventory: dict[str, int]) -> int:
    if complete_sets(inventory) > 0:
        return 0x57F287  # green
    if any(inventory.values()):
        return 0x5865F2  # blurple
    return 0x99AAB5  # gray


def _format_items(
    inventory: dict[str, int],
    present: Callable[[str], str],
    missing: Callable[[str], str],
    footer: str | None = None,
) -> str:
    lines = []
    for item in ITEMS:
        count = inventory.get(item, 0)
        if count > 0:
            suffix = f" ×{count}" if count > 1 else ""
            lines.append(present(item) + suffix)
        else:
            lines.append(missing(item))
    if footer is not None:
        lines.append(footer)
    return "\n".join(lines)


def format_field(inventory: dict[str, int]) -> str:
    sets = complete_sets(inventory)
    footer = f"🏆 **{sets} set{'s' if sets != 1 else ''}**" if sets else "*no complete set*"
    return _format_items(
        inventory,
        present=lambda item: f"✅ {item.removeprefix('DCHS-')}",
        missing=lambda item: f"❌ {item.removeprefix('DCHS-')}",
        footer=footer,
    )


def build_status_table(
    active: dict[str, dict[str, int]],
    member_names: dict[str, str],
) -> str:
    lines = []
    for user_key, user_inv in sorted(active.items(), key=lambda kv: complete_sets(kv[1]), reverse=True):
        name = member_names.get(user_key)
        if name is None:
            continue
        card_parts = " · ".join(
            f"{item.removeprefix('DCHS-')}:×{user_inv.get(item, 0)}" for item in ITEMS
        )
        sets = complete_sets(user_inv)
        lines.append(f"**{name}** · {card_parts} · Sets: ×{sets}")
    return "\n".join(lines)


def format_mine(inventory: dict[str, int]) -> str:
    return _format_items(
        inventory,
        present=lambda item: f"✅ **{item}**",
        missing=lambda item: f"❌ ~~{item}~~",
    )


async def get_guild_inventory(cog, guild_id: int) -> dict[str, dict[str, int]]:
    return await cog.bot.state.get(guild_key(guild_id), {})


async def save_guild_inventory(cog, guild_id: int, data: dict[str, dict[str, int]]) -> None:
    await cog.bot.state.set(guild_key(guild_id), data)
