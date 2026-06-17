from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from src.starcitizenwiki_api import StarCitizenWikiError
from src.starcitizenwiki_api.client import NotFoundError
from src.commands.armor import build_armor_embed
from src.commands.clothes import build_clothes_embed
from src.commands.item import build_item_embed
from src.commands.ship_weapons import build_ship_weapon_embed
from src.commands.vehicle_item import build_vehicle_item_embed
from src.commands.weapon_attachment import build_weapon_attachment_embed
from src.commands.weapons import build_weapon_embed

DISPATCH = {
    "weapon": ("weapons_api", build_weapon_embed),
    "ship-weapon": ("ship_weapons_api", build_ship_weapon_embed),
    "armor": ("armor_api", build_armor_embed),
    "clothes": ("clothes_api", build_clothes_embed),
    "vehicle-item": ("vehicle_items_api", build_vehicle_item_embed),
    "weapon-attachment": ("weapon_attachments_api", build_weapon_attachment_embed),
    "item": ("items_api", build_item_embed),
}

_CATEGORIES = [
    ("weapon", "Weapon"),
    ("ship-weapon", "Ship Weapon"),
    ("armor", "Armor"),
    ("clothes", "Clothing"),
    ("vehicle-item", "Vehicle Item"),
    ("weapon-attachment", "Weapon Attachment"),
    ("item", "Item"),
]

_API_ATTRS = [
    "weapons_api",
    "ship_weapons_api",
    "armor_api",
    "clothes_api",
    "vehicle_items_api",
    "weapon_attachments_api",
    "items_api",
]


class FindCog(commands.Cog):
    find = app_commands.Group(name="find", description="Search Star Citizen items by type")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --- autocomplete helpers ---

    async def _single_autocomplete(
        self, api_attr: str, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for one category; choice value is the raw slug."""
        if not current:
            return []
        try:
            results = await getattr(self.bot, api_attr).search(current, limit=25)
        except Exception:
            return []
        choices: list[app_commands.Choice[str]] = []
        seen: set[str] = set()
        for item in sorted(results, key=lambda x: len(x.name)):
            if item.name in seen:
                continue
            seen.add(item.name)
            identifier = item.slug or item.name
            choices.append(app_commands.Choice(name=item.name[:100], value=identifier[:100]))
            if len(choices) >= 25:
                break
        return choices

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
        """Autocomplete across all categories; choice value is category_key:slug."""
        if not current:
            return []
        results = await asyncio.gather(
            *[getattr(self.bot, attr).search(current, limit=5) for attr in _API_ATTRS],
            return_exceptions=True,
        )
        choices: list[app_commands.Choice[str]] = []
        global_seen: set[str] = set()
        for (category_key, category_label), result in zip(_CATEGORIES, results):
            if isinstance(result, Exception):
                continue
            for item in sorted(result, key=lambda x: len(x.name)):
                if item.name in global_seen:
                    continue
                global_seen.add(item.name)
                identifier = item.slug or item.name
                choices.append(
                    app_commands.Choice(
                        name=f"{item.name} ({category_label})"[:100],
                        value=f"{category_key}:{identifier}"[:100],
                    )
                )
                if len(choices) >= 25:
                    return choices
        return choices

    # --- shared handler ---

    async def _handle_single(
        self, interaction: discord.Interaction, name: str, category_key: str
    ) -> None:
        await interaction.response.defer()
        api_attr, embed_builder = DISPATCH[category_key]
        api = getattr(self.bot, api_attr)
        try:
            try:
                item = await api.get(name)
            except NotFoundError:
                item = await api.find(name)
        except StarCitizenWikiError as e:
            await interaction.followup.send(
                f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True
            )
            return
        if item is None:
            await interaction.followup.send(
                f"No item found matching **{name}**.", ephemeral=True
            )
            return
        await interaction.followup.send(embed=embed_builder(item))

    # --- subcommands ---

    @find.command(name="all", description="Search across all item types at once")
    @app_commands.describe(name="Item name to search for")
    @app_commands.autocomplete(name=all_autocomplete)
    async def all(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer()
        category_key, _, identifier = name.partition(":")
        if not identifier:
            await interaction.followup.send(
                "Please select a result from the autocomplete list.", ephemeral=True
            )
            return
        entry = DISPATCH.get(category_key)
        if entry is None:
            await interaction.followup.send(
                f"Unknown category **{category_key}**.", ephemeral=True
            )
            return
        api_attr, embed_builder = entry
        api = getattr(self.bot, api_attr)
        try:
            try:
                item = await api.get(identifier)
            except NotFoundError:
                item = await api.find(identifier)
        except StarCitizenWikiError as e:
            await interaction.followup.send(
                f"Couldn't reach the Star Citizen Wiki API right now: {e}", ephemeral=True
            )
            return
        if item is None:
            await interaction.followup.send(
                f"No item found matching **{identifier}**.", ephemeral=True
            )
            return
        await interaction.followup.send(embed=embed_builder(item))

    @find.command(name="weapon", description="Search FPS weapons")
    @app_commands.describe(name="Weapon name to search for")
    @app_commands.autocomplete(name=weapon_autocomplete)
    async def weapon(self, interaction: discord.Interaction, name: str) -> None:
        await self._handle_single(interaction, name, "weapon")

    @find.command(name="shipweapon", description="Search ship-mounted weapons")
    @app_commands.describe(name="Ship weapon name to search for")
    @app_commands.autocomplete(name=shipweapon_autocomplete)
    async def shipweapon(self, interaction: discord.Interaction, name: str) -> None:
        await self._handle_single(interaction, name, "ship-weapon")

    @find.command(name="armor", description="Search armor")
    @app_commands.describe(name="Armor name to search for")
    @app_commands.autocomplete(name=armor_autocomplete)
    async def armor(self, interaction: discord.Interaction, name: str) -> None:
        await self._handle_single(interaction, name, "armor")

    @find.command(name="clothes", description="Search clothing")
    @app_commands.describe(name="Clothing name to search for")
    @app_commands.autocomplete(name=clothes_autocomplete)
    async def clothes(self, interaction: discord.Interaction, name: str) -> None:
        await self._handle_single(interaction, name, "clothes")

    @find.command(name="vehicleitem", description="Search vehicle/ship components")
    @app_commands.describe(name="Component name to search for")
    @app_commands.autocomplete(name=vehicleitem_autocomplete)
    async def vehicleitem(self, interaction: discord.Interaction, name: str) -> None:
        await self._handle_single(interaction, name, "vehicle-item")

    @find.command(name="weaponattachment", description="Search FPS weapon attachments")
    @app_commands.describe(name="Attachment name to search for")
    @app_commands.autocomplete(name=weaponattachment_autocomplete)
    async def weaponattachment(self, interaction: discord.Interaction, name: str) -> None:
        await self._handle_single(interaction, name, "weapon-attachment")

    @find.command(name="item", description="Search miscellaneous items")
    @app_commands.describe(name="Item name to search for")
    @app_commands.autocomplete(name=item_autocomplete)
    async def item(self, interaction: discord.Interaction, name: str) -> None:
        await self._handle_single(interaction, name, "item")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FindCog(bot))
