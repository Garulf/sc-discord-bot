"""Shared helpers for building Discord slash-command autocomplete choices.

Every command's autocomplete does the same thing: turn a list of results into
de-duplicated :class:`app_commands.Choice` values, capped and length-trimmed to
Discord's limits. These helpers capture that so each cog only decides what to
search and how to sort.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from discord import app_commands

# Discord limits: a choice label/value is at most 100 chars, and at most 25
# choices are returned per autocomplete response.
MAX_CHOICE_LABEL = 100
MAX_AUTOCOMPLETE_CHOICES = 25


def _trim(text: str) -> str:
    return text[:MAX_CHOICE_LABEL]


def name_choices(names: Iterable[str]) -> list[app_commands.Choice[str]]:
    """Build choices whose label and value are both the name, de-duplicated."""
    choices: list[app_commands.Choice[str]] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        choices.append(app_commands.Choice(name=_trim(name), value=_trim(name)))
        if len(choices) >= MAX_AUTOCOMPLETE_CHOICES:
            break
    return choices


class _Named(Protocol):
    name: str
    slug: str | None


def item_choices(items: Iterable[_Named], *, use_slug: bool = False) -> list[app_commands.Choice[str]]:
    """Build choices from wiki items, de-duplicated by display name.

    The label is the item name. The value is the item's slug when ``use_slug``
    is set and a slug exists (so the command can fetch it directly), else the
    name. Callers sort ``items`` first if they want a particular order.
    """
    choices: list[app_commands.Choice[str]] = []
    seen: set[str] = set()
    for item in items:
        if item.name in seen:
            continue
        seen.add(item.name)
        value = (item.slug or item.name) if use_slug else item.name
        choices.append(app_commands.Choice(name=_trim(item.name), value=_trim(value)))
        if len(choices) >= MAX_AUTOCOMPLETE_CHOICES:
            break
    return choices
