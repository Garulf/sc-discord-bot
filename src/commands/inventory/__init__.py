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
        item="DCHS item to add",     item2="DCHS item to add",  item3="DCHS item to add",
        item4="DCHS item to add",    item5="DCHS item to add",  item6="DCHS item to add",
        item7="DCHS item to add",    item8="DCHS item to add",  item9="DCHS item to add",
        item10="DCHS item to add",   item11="DCHS item to add", item12="DCHS item to add",
        item13="DCHS item to add",   item14="DCHS item to add", item15="DCHS item to add",
        item16="DCHS item to add",   item17="DCHS item to add", item18="DCHS item to add",
        item19="DCHS item to add",   item20="DCHS item to add", item21="DCHS item to add",
        item22="DCHS item to add",   item23="DCHS item to add", item24="DCHS item to add",
        item25="DCHS item to add",
    )
    @app_commands.autocomplete(
        item=item_autocomplete,   item2=item_autocomplete,  item3=item_autocomplete,
        item4=item_autocomplete,  item5=item_autocomplete,  item6=item_autocomplete,
        item7=item_autocomplete,  item8=item_autocomplete,  item9=item_autocomplete,
        item10=item_autocomplete, item11=item_autocomplete, item12=item_autocomplete,
        item13=item_autocomplete, item14=item_autocomplete, item15=item_autocomplete,
        item16=item_autocomplete, item17=item_autocomplete, item18=item_autocomplete,
        item19=item_autocomplete, item20=item_autocomplete, item21=item_autocomplete,
        item22=item_autocomplete, item23=item_autocomplete, item24=item_autocomplete,
        item25=item_autocomplete,
    )
    async def add(
        self,
        interaction: discord.Interaction,
        item: str,
        item2: str | None = None,  item3: str | None = None,  item4: str | None = None,
        item5: str | None = None,  item6: str | None = None,  item7: str | None = None,
        item8: str | None = None,  item9: str | None = None,  item10: str | None = None,
        item11: str | None = None, item12: str | None = None, item13: str | None = None,
        item14: str | None = None, item15: str | None = None, item16: str | None = None,
        item17: str | None = None, item18: str | None = None, item19: str | None = None,
        item20: str | None = None, item21: str | None = None, item22: str | None = None,
        item23: str | None = None, item24: str | None = None, item25: str | None = None,
    ) -> None:
        items = [i for i in [
            item, item2, item3, item4, item5, item6, item7, item8, item9, item10,
            item11, item12, item13, item14, item15, item16, item17, item18, item19, item20,
            item21, item22, item23, item24, item25,
        ] if i is not None]
        await _handle_add(self, interaction, items)

    @remove_group.command(name="item", description="Remove one or more DCHS items from your inventory")
    @app_commands.describe(
        item="DCHS item to remove",     item2="DCHS item to remove",  item3="DCHS item to remove",
        item4="DCHS item to remove",    item5="DCHS item to remove",  item6="DCHS item to remove",
        item7="DCHS item to remove",    item8="DCHS item to remove",  item9="DCHS item to remove",
        item10="DCHS item to remove",   item11="DCHS item to remove", item12="DCHS item to remove",
        item13="DCHS item to remove",   item14="DCHS item to remove", item15="DCHS item to remove",
        item16="DCHS item to remove",   item17="DCHS item to remove", item18="DCHS item to remove",
        item19="DCHS item to remove",   item20="DCHS item to remove", item21="DCHS item to remove",
        item22="DCHS item to remove",   item23="DCHS item to remove", item24="DCHS item to remove",
        item25="DCHS item to remove",
    )
    @app_commands.autocomplete(
        item=item_autocomplete,   item2=item_autocomplete,  item3=item_autocomplete,
        item4=item_autocomplete,  item5=item_autocomplete,  item6=item_autocomplete,
        item7=item_autocomplete,  item8=item_autocomplete,  item9=item_autocomplete,
        item10=item_autocomplete, item11=item_autocomplete, item12=item_autocomplete,
        item13=item_autocomplete, item14=item_autocomplete, item15=item_autocomplete,
        item16=item_autocomplete, item17=item_autocomplete, item18=item_autocomplete,
        item19=item_autocomplete, item20=item_autocomplete, item21=item_autocomplete,
        item22=item_autocomplete, item23=item_autocomplete, item24=item_autocomplete,
        item25=item_autocomplete,
    )
    async def remove_item(
        self,
        interaction: discord.Interaction,
        item: str,
        item2: str | None = None,  item3: str | None = None,  item4: str | None = None,
        item5: str | None = None,  item6: str | None = None,  item7: str | None = None,
        item8: str | None = None,  item9: str | None = None,  item10: str | None = None,
        item11: str | None = None, item12: str | None = None, item13: str | None = None,
        item14: str | None = None, item15: str | None = None, item16: str | None = None,
        item17: str | None = None, item18: str | None = None, item19: str | None = None,
        item20: str | None = None, item21: str | None = None, item22: str | None = None,
        item23: str | None = None, item24: str | None = None, item25: str | None = None,
    ) -> None:
        items = [i for i in [
            item, item2, item3, item4, item5, item6, item7, item8, item9, item10,
            item11, item12, item13, item14, item15, item16, item17, item18, item19, item20,
            item21, item22, item23, item24, item25,
        ] if i is not None]
        await _handle_remove(self, interaction, items)

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
