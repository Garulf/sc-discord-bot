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
from .remove_set import handle as _handle_remove_set
from .shared import item_choices
from .status.everyone import handle as _handle_status_everyone
from .status.mine import handle as _handle_status_mine


class InventoryCog(commands.Cog):
    """DCHS collectible set inventory tracking."""

    inventory = app_commands.Group(name="inventory", description="DCHS collectible set inventory")

    remove_group = app_commands.Group(
        name="remove",
        description="Remove DCHS items from your inventory",
        parent=inventory,
    )

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

    @inventory.command(name="add", description="Add one or more DCHS items to your inventory")
    @app_commands.describe(
        item="First DCHS item to add",
        count="Quantity of first item (default 1)",
        item2="Second DCHS item to add",
        count2="Quantity (default 1)",
        item3="Third DCHS item to add",
        count3="Quantity (default 1)",
        item4="Fourth DCHS item to add",
        count4="Quantity (default 1)",
        item5="Fifth DCHS item to add",
        count5="Quantity (default 1)",
        item6="Sixth DCHS item to add",
        count6="Quantity (default 1)",
        item7="Seventh DCHS item to add",
        count7="Quantity (default 1)",
    )
    @app_commands.autocomplete(
        item=item_autocomplete,
        item2=item_autocomplete,
        item3=item_autocomplete,
        item4=item_autocomplete,
        item5=item_autocomplete,
        item6=item_autocomplete,
        item7=item_autocomplete,
    )
    async def add(
        self,
        interaction: discord.Interaction,
        item: str,
        count: int = 1,
        item2: str | None = None,
        count2: int = 1,
        item3: str | None = None,
        count3: int = 1,
        item4: str | None = None,
        count4: int = 1,
        item5: str | None = None,
        count5: int = 1,
        item6: str | None = None,
        count6: int = 1,
        item7: str | None = None,
        count7: int = 1,
    ) -> None:
        entries = [(item, count)]
        for i, c in [(item2, count2), (item3, count3), (item4, count4), (item5, count5), (item6, count6), (item7, count7)]:
            if i is not None:
                entries.append((i, c))
        await _handle_add(self, interaction, entries)

    @remove_group.command(name="item", description="Remove a DCHS item from your inventory")
    @app_commands.describe(item="The DCHS item to remove", count="How many to remove (default 1)")
    @app_commands.autocomplete(item=item_autocomplete)
    async def remove_item(self, interaction: discord.Interaction, item: str, count: int = 1) -> None:
        await _handle_remove(self, interaction, item, count)

    @remove_group.command(name="set", description="Remove one complete set (DCHS-01 through DCHS-07) from your inventory")
    async def remove_set(self, interaction: discord.Interaction) -> None:
        await _handle_remove_set(self, interaction)

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
