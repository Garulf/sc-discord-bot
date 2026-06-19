"""The /find command group: cross-category item search across all Star Citizen
Wiki APIs. Subcommand logic lives in individual files; this module contains
only the Cog class (autocomplete, command registration)."""

from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.autocomplete import MAX_AUTOCOMPLETE_CHOICES, MAX_CHOICE_LABEL, item_choices

from .all import handle as _handle_all
from .armor import handle as _handle_armor
from .clothes import handle as _handle_clothes
from .dispatch import API_ATTRS, CATEGORIES, DISPATCH
from .item import handle as _handle_item
from .shipweapon import handle as _handle_shipweapon
from .vehicleitem import handle as _handle_vehicleitem
from .weapon import handle as _handle_weapon
from .weaponattachment import handle as _handle_weaponattachment


class FindCog(commands.Cog):
    """Cross-category item search across all Star Citizen Wiki APIs."""

    find = app_commands.Group(name="find", description="Search Star Citizen items by type")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _handle_single(self, interaction: discord.Interaction, name: str, category_key: str) -> None:
        from src.starcitizenwiki_api import StarCitizenWikiError
        from src.starcitizenwiki_api.client import NotFoundError

        await interaction.response.defer()
        api_attr, embed_builder = DISPATCH[category_key]
        api = getattr(self.bot, api_attr)
        try:
            try:
                item = await api.get(name)
            except NotFoundError:
                item = await api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True)
            return
        if item is None:
            await interaction.followup.send(f"No item found matching **{name}**.", ephemeral=True)
            return
        await interaction.followup.send(embed=embed_builder(item))

    async def _single_autocomplete(self, api_attr: str, current: str) -> list[app_commands.Choice[str]]:
        if not current:
            return []
        try:
            results = await getattr(self.bot, api_attr).search(current, limit=25)
        except Exception:  # noqa: BLE001 - autocomplete failures are silently dropped
            return []
        return item_choices(sorted(results, key=lambda x: len(x.name)), use_slug=True)

    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._single_autocomplete("weapons_api", current)

    async def shipweapon_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._single_autocomplete("ship_weapons_api", current)

    async def armor_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._single_autocomplete("armor_api", current)

    async def clothes_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._single_autocomplete("clothes_api", current)

    async def vehicleitem_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._single_autocomplete("vehicle_items_api", current)

    async def weaponattachment_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._single_autocomplete("weapon_attachments_api", current)

    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._single_autocomplete("items_api", current)

    async def all_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete across all categories; choice value is ``category_key:slug``."""
        if not current:
            return []
        results = await asyncio.gather(
            *[getattr(self.bot, attr).search(current, limit=5) for attr in API_ATTRS],
            return_exceptions=True,
        )
        choices: list[app_commands.Choice[str]] = []
        global_seen: set[str] = set()
        for (category_key, category_label), result in zip(CATEGORIES, results):
            if isinstance(result, Exception):
                continue
            for item in sorted(result, key=lambda x: len(x.name)):
                if item.name in global_seen:
                    continue
                global_seen.add(item.name)
                identifier = item.slug or item.name
                choices.append(
                    app_commands.Choice(
                        name=f"{item.name} ({category_label})"[:MAX_CHOICE_LABEL],
                        value=f"{category_key}:{identifier}"[:MAX_CHOICE_LABEL],
                    )
                )
                if len(choices) >= MAX_AUTOCOMPLETE_CHOICES:
                    return choices
        return choices

    @find.command(name="all", description="Search across all item types at once")
    @app_commands.describe(name="Item name to search for")
    @app_commands.autocomplete(name=all_autocomplete)
    async def all(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_all(self, interaction, name)

    @find.command(name="weapon", description="Search FPS weapons")
    @app_commands.describe(name="Weapon name to search for")
    @app_commands.autocomplete(name=weapon_autocomplete)
    async def weapon(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_weapon(self, interaction, name)

    @find.command(name="shipweapon", description="Search ship-mounted weapons")
    @app_commands.describe(name="Ship weapon name to search for")
    @app_commands.autocomplete(name=shipweapon_autocomplete)
    async def shipweapon(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_shipweapon(self, interaction, name)

    @find.command(name="armor", description="Search armor")
    @app_commands.describe(name="Armor name to search for")
    @app_commands.autocomplete(name=armor_autocomplete)
    async def armor(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_armor(self, interaction, name)

    @find.command(name="clothes", description="Search clothing")
    @app_commands.describe(name="Clothing name to search for")
    @app_commands.autocomplete(name=clothes_autocomplete)
    async def clothes(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_clothes(self, interaction, name)

    @find.command(name="vehicleitem", description="Search vehicle/ship components")
    @app_commands.describe(name="Component name to search for")
    @app_commands.autocomplete(name=vehicleitem_autocomplete)
    async def vehicleitem(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_vehicleitem(self, interaction, name)

    @find.command(name="weaponattachment", description="Search FPS weapon attachments")
    @app_commands.describe(name="Attachment name to search for")
    @app_commands.autocomplete(name=weaponattachment_autocomplete)
    async def weaponattachment(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_weaponattachment(self, interaction, name)

    @find.command(name="item", description="Search miscellaneous items")
    @app_commands.describe(name="Item name to search for")
    @app_commands.autocomplete(name=item_autocomplete)
    async def item(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_item(self, interaction, name)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FindCog(bot))
