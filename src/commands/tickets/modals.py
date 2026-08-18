"""Category-specific modals for opening tickets from the panel buttons."""

from __future__ import annotations

import discord

from .categories import CATEGORIES, short_label
from .lifecycle import open_ticket

_LOCATION_KEYS = {"location", "route_from", "route_to"}
_LOCATION_PLACEHOLDER = "Stanton:Hurston:Lorville"
_MAX_VALUE_LENGTH = 200


class TicketModal(discord.ui.Modal):
    def __init__(self, cog, category_key: str) -> None:
        category = CATEGORIES[category_key]
        super().__init__(title=f"{short_label(category)} ticket", custom_id=f"tickets:modal:{category_key}")
        self._cog = cog
        self.category_key = category_key
        self._field_keys: dict[discord.ui.TextInput, str] = {}
        for spec in category.fields:
            component = discord.ui.TextInput(
                required=spec.required,
                placeholder=_LOCATION_PLACEHOLDER if spec.key in _LOCATION_KEYS else None,
                max_length=_MAX_VALUE_LENGTH,
            )
            self._field_keys[component] = spec.key
            self.add_item(discord.ui.Label(text=spec.label, component=component))

    def field_key(self, item: discord.ui.TextInput) -> str:
        return self._field_keys[item]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        fields = {}
        for item, key in self._field_keys.items():
            value = (item.value or "").strip()
            if value:
                fields[key] = value
        await open_ticket(self._cog, interaction, self.category_key, fields)
