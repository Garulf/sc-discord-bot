"""The /find command group: cross-category item search across all Star Citizen
Wiki APIs. Subcommand logic lives in individual files; shared lookup and
autocomplete logic lives in shared.py."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .all import handle as _handle_all
from .armor import handle as _handle_armor
from .blueprint import autocomplete as _blueprint_autocomplete
from .blueprint import handle as _handle_blueprint
from .clothes import handle as _handle_clothes
from .item import handle as _handle_item
from .shared import autocomplete_all, autocomplete_single
from .shipweapon import handle as _handle_shipweapon
from .vehicleitem import handle as _handle_vehicleitem
from .weapon import handle as _handle_weapon
from .weaponattachment import handle as _handle_weaponattachment


class FindCog(commands.Cog):
    """Cross-category item search across all Star Citizen Wiki APIs."""

    find = app_commands.Group(name="find", description="Search Star Citizen items by type")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def weapon_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_single(self, "weapons_api", current)

    async def shipweapon_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_single(self, "ship_weapons_api", current)

    async def armor_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_single(self, "armor_api", current)

    async def clothes_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_single(self, "clothes_api", current)

    async def vehicleitem_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_single(self, "vehicle_items_api", current)

    async def weaponattachment_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_single(self, "weapon_attachments_api", current)

    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_single(self, "items_api", current)

    async def blueprint_autocomplete(self, interaction: discord.Interaction, current: str):
        return await _blueprint_autocomplete(self, current)

    async def all_autocomplete(self, interaction: discord.Interaction, current: str):
        return await autocomplete_all(self, current)

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

    @find.command(name="blueprint", description="Search Star Citizen crafting blueprints")
    @app_commands.describe(name="Blueprint name to search for")
    @app_commands.autocomplete(name=blueprint_autocomplete)
    async def blueprint(self, interaction: discord.Interaction, name: str) -> None:
        await _handle_blueprint(self, interaction, name)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FindCog(bot))
