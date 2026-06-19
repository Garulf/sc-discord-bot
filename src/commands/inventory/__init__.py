"""Inventory tracking for DCHS collectible sets.

Each user's per-guild inventory is persisted in the bot's SQLite StateStore
under a key scoped to the guild. The ``/inventory status`` command resolves
Discord member display names at call time so display names stay current.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from .add import handle as _handle_add
from .admin.add import handle as _handle_admin_add
from .admin.clear import handle as _handle_admin_clear
from .admin.clear_all import handle as _handle_admin_clear_all
from .admin.remove import handle as _handle_admin_remove
from .clear import handle as _handle_clear
from .remove import handle as _handle_remove
from .shared import item_choices
from .status.everyone import handle as _handle_status_everyone
from .status.mine import handle as _handle_status_mine


class InventoryCog(commands.Cog):
    """DCHS collectible set inventory tracking."""

    inventory = app_commands.Group(name="inventory", description="DCHS collectible set inventory")

    status_group = app_commands.Group(
        name="status",
        description="View DCHS inventory status",
        parent=inventory,
    )

    admin_group = app_commands.Group(
        name="admin",
        description="Manage other members' DCHS inventories (admins/sc-bot only)",
        parent=inventory,
        default_permissions=discord.Permissions(administrator=True),
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def item_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return item_choices(current)

    @inventory.command(name="add", description="Add a DCHS item to your inventory")
    @app_commands.describe(item="The DCHS item to add (DCHS-01 through DCHS-07)", count="How many to add (default 1)")
    @app_commands.autocomplete(item=item_autocomplete)
    async def add(self, interaction: discord.Interaction, item: str, count: int = 1) -> None:
        await _handle_add(self, interaction, item, count)

    @inventory.command(name="remove", description="Remove a DCHS item from your inventory")
    @app_commands.describe(item="The DCHS item to remove", count="How many to remove (default 1)")
    @app_commands.autocomplete(item=item_autocomplete)
    async def remove(self, interaction: discord.Interaction, item: str, count: int = 1) -> None:
        await _handle_remove(self, interaction, item, count)

    @inventory.command(name="clear", description="Clear all DCHS items from your inventory")
    async def clear(self, interaction: discord.Interaction) -> None:
        await _handle_clear(self, interaction)

    @status_group.command(name="mine", description="Show your own DCHS inventory")
    async def status_mine(self, interaction: discord.Interaction) -> None:
        await _handle_status_mine(self, interaction)

    @status_group.command(name="everyone", description="Show all members' DCHS inventory and complete sets")
    async def status_everyone(self, interaction: discord.Interaction) -> None:
        await _handle_status_everyone(self, interaction)

    @admin_group.command(name="add", description="Add a DCHS item to a member's inventory")
    @app_commands.describe(
        member="The member to add the item for",
        item="The DCHS item to add (DCHS-01 through DCHS-07)",
        count="How many to add (default 1)",
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def admin_add(
        self, interaction: discord.Interaction, member: discord.Member, item: str, count: int = 1
    ) -> None:
        await _handle_admin_add(self, interaction, member, item, count)

    @admin_group.command(name="remove", description="Remove a DCHS item from a member's inventory")
    @app_commands.describe(
        member="The member to remove the item from",
        item="The DCHS item to remove",
        count="How many to remove (default 1)",
    )
    @app_commands.autocomplete(item=item_autocomplete)
    async def admin_remove(
        self, interaction: discord.Interaction, member: discord.Member, item: str, count: int = 1
    ) -> None:
        await _handle_admin_remove(self, interaction, member, item, count)

    @admin_group.command(name="clear", description="Clear all DCHS items from a member's inventory")
    @app_commands.describe(member="The member whose inventory to clear")
    async def admin_clear(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await _handle_admin_clear(self, interaction, member)

    @admin_group.command(name="clear-all", description="Clear all members' inventories")
    async def admin_clear_all(self, interaction: discord.Interaction) -> None:
        await _handle_admin_clear_all(self, interaction)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InventoryCog(bot))
