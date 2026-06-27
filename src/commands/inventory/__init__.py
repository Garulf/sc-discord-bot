"""Inventory tracking for DCHS collectible sets.

Each user's per-guild inventory is persisted in the bot's SQLite StateStore
under a key scoped to the guild. The ``/inventory status`` command resolves
Discord member display names at call time so display names stay current.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot, handle_check_failure

from .add import handle as _handle_add
from .admin.add import handle as _handle_admin_add
from .admin.clear import handle as _handle_admin_clear
from .admin.clear_all import handle as _handle_admin_clear_all
from .admin.remove import handle as _handle_admin_remove
from .admin.transfer_set import handle as _handle_admin_transfer_set
from .clear import handle as _handle_clear
from .remove import handle as _handle_remove
from .remove_set import handle as _handle_remove_set
from .status.everyone import handle as _handle_status_everyone
from .status.mine import handle as _handle_status_mine
from .subscribe import handle as _handle_subscribe
from .subscriptions import cleanup_expired_notifications, refresh_live_status
from .transfer import handle as _handle_transfer
from .transfer_set import handle as _handle_transfer_set
from .unsubscribe import handle as _handle_unsubscribe

logger = logging.getLogger(__name__)


async def _count_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    options = ["1", "2", "3", "4", "5"]
    return [
        app_commands.Choice(name=v, value=v)
        for v in options
        if v.startswith(current)
    ]


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

    transfer_group = app_commands.Group(
        name="transfer",
        description="Transfer DCHS items to another member",
        parent=inventory,
    )

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.cleanup_loop.start()
        self.refresh_loop.start()

    async def cog_unload(self) -> None:
        self.cleanup_loop.cancel()
        self.refresh_loop.cancel()

    @tasks.loop(minutes=10)
    async def cleanup_loop(self) -> None:
        for guild in self.bot.guilds:
            await cleanup_expired_notifications(self, guild.id)

    @cleanup_loop.before_loop
    async def before_cleanup_loop(self) -> None:
        await self.bot.wait_until_ready()

    @cleanup_loop.error
    async def cleanup_loop_error(self, error: Exception) -> None:
        logger.exception("Inventory cleanup loop error: %s", error)

    @tasks.loop(minutes=5)
    async def refresh_loop(self) -> None:
        for guild in self.bot.guilds:
            await refresh_live_status(self, guild.id)

    @refresh_loop.before_loop
    async def before_refresh_loop(self) -> None:
        await self.bot.wait_until_ready()
        try:
            for guild in self.bot.guilds:
                await refresh_live_status(self, guild.id)
        except Exception:
            logger.exception("Error during initial inventory refresh")

    @refresh_loop.error
    async def refresh_loop_error(self, error: Exception) -> None:
        logger.exception("Inventory refresh loop error: %s", error)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await handle_check_failure(interaction, error)
            return
        logger.exception("Unhandled error in inventory command: %s", error)
        msg = "Something went wrong. Check the bot logs for details."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    @inventory.command(name="add", description="Add DCHS cards to your inventory")
    @app_commands.rename(
        dchs_01="dchs-01", dchs_02="dchs-02", dchs_03="dchs-03",
        dchs_04="dchs-04", dchs_05="dchs-05", dchs_06="dchs-06", dchs_07="dchs-07",
    )
    @app_commands.describe(
        dchs_01="Count to add (default 1)",
        dchs_02="Count to add (default 1)",
        dchs_03="Count to add (default 1)",
        dchs_04="Count to add (default 1)",
        dchs_05="Count to add (default 1)",
        dchs_06="Count to add (default 1)",
        dchs_07="Count to add (default 1)",
    )
    @app_commands.autocomplete(
        dchs_01=_count_autocomplete, dchs_02=_count_autocomplete,
        dchs_03=_count_autocomplete, dchs_04=_count_autocomplete,
        dchs_05=_count_autocomplete, dchs_06=_count_autocomplete,
        dchs_07=_count_autocomplete,
    )
    async def add(
        self,
        interaction: discord.Interaction,
        dchs_01: str | None = None,
        dchs_02: str | None = None,
        dchs_03: str | None = None,
        dchs_04: str | None = None,
        dchs_05: str | None = None,
        dchs_06: str | None = None,
        dchs_07: str | None = None,
    ) -> None:
        raw_pairs = [
            ("DCHS-01", dchs_01), ("DCHS-02", dchs_02), ("DCHS-03", dchs_03),
            ("DCHS-04", dchs_04), ("DCHS-05", dchs_05), ("DCHS-06", dchs_06),
            ("DCHS-07", dchs_07),
        ]
        entries = []
        for item, raw in raw_pairs:
            if raw is None:
                continue
            count = int(raw.strip()) if raw.strip().isdigit() else 1
            entries.append((item, count))
        if not entries:
            await interaction.response.send_message("Please specify at least one card.", ephemeral=True)
            return
        await _handle_add(self, interaction, entries)

    @remove_group.command(name="item", description="Remove DCHS cards from your inventory")
    @app_commands.rename(
        dchs_01="dchs-01", dchs_02="dchs-02", dchs_03="dchs-03",
        dchs_04="dchs-04", dchs_05="dchs-05", dchs_06="dchs-06", dchs_07="dchs-07",
    )
    @app_commands.describe(
        dchs_01="Number of DCHS-01 to remove",
        dchs_02="Number of DCHS-02 to remove",
        dchs_03="Number of DCHS-03 to remove",
        dchs_04="Number of DCHS-04 to remove",
        dchs_05="Number of DCHS-05 to remove",
        dchs_06="Number of DCHS-06 to remove",
        dchs_07="Number of DCHS-07 to remove",
    )
    async def remove_item(
        self,
        interaction: discord.Interaction,
        dchs_01: int | None = None,
        dchs_02: int | None = None,
        dchs_03: int | None = None,
        dchs_04: int | None = None,
        dchs_05: int | None = None,
        dchs_06: int | None = None,
        dchs_07: int | None = None,
    ) -> None:
        entries = [
            (item, count) for item, count in [
                ("DCHS-01", dchs_01), ("DCHS-02", dchs_02), ("DCHS-03", dchs_03),
                ("DCHS-04", dchs_04), ("DCHS-05", dchs_05), ("DCHS-06", dchs_06),
                ("DCHS-07", dchs_07),
            ] if count is not None
        ]
        if not entries:
            await interaction.response.send_message("Please specify at least one card.", ephemeral=True)
            return
        await _handle_remove(self, interaction, entries)

    @remove_group.command(name="set", description="Remove one complete set (DCHS-01 through DCHS-07) from your inventory")
    async def remove_set(self, interaction: discord.Interaction) -> None:
        await _handle_remove_set(self, interaction)

    @inventory.command(name="clear", description="Clear all DCHS items from your inventory")
    async def clear(self, interaction: discord.Interaction) -> None:
        await _handle_clear(self, interaction)

    @transfer_group.command(name="item", description="Transfer DCHS cards from your inventory to another member")
    @app_commands.rename(
        dchs_01="dchs-01", dchs_02="dchs-02", dchs_03="dchs-03",
        dchs_04="dchs-04", dchs_05="dchs-05", dchs_06="dchs-06", dchs_07="dchs-07",
    )
    @app_commands.describe(
        recipient="The member to receive the cards",
        dchs_01="Number of DCHS-01 to transfer",
        dchs_02="Number of DCHS-02 to transfer",
        dchs_03="Number of DCHS-03 to transfer",
        dchs_04="Number of DCHS-04 to transfer",
        dchs_05="Number of DCHS-05 to transfer",
        dchs_06="Number of DCHS-06 to transfer",
        dchs_07="Number of DCHS-07 to transfer",
    )
    async def transfer_item(
        self,
        interaction: discord.Interaction,
        recipient: discord.Member,
        dchs_01: int | None = None,
        dchs_02: int | None = None,
        dchs_03: int | None = None,
        dchs_04: int | None = None,
        dchs_05: int | None = None,
        dchs_06: int | None = None,
        dchs_07: int | None = None,
    ) -> None:
        entries = [
            (item, count) for item, count in [
                ("DCHS-01", dchs_01), ("DCHS-02", dchs_02), ("DCHS-03", dchs_03),
                ("DCHS-04", dchs_04), ("DCHS-05", dchs_05), ("DCHS-06", dchs_06),
                ("DCHS-07", dchs_07),
            ] if count is not None
        ]
        if not entries:
            await interaction.response.send_message("Please specify at least one card to transfer.", ephemeral=True)
            return
        await _handle_transfer(self, interaction, recipient, entries)

    @transfer_group.command(name="set", description="Transfer one complete set (DCHS-01 through DCHS-07) to another member")
    @app_commands.describe(recipient="The member to receive the set")
    async def transfer_set_cmd(self, interaction: discord.Interaction, recipient: discord.Member) -> None:
        await _handle_transfer_set(self, interaction, recipient)

    @inventory.command(name="subscribe", description="Post a live DCHS inventory status in this channel")
    @app_commands.check(admin_or_sc_bot)
    async def subscribe(self, interaction: discord.Interaction) -> None:
        await _handle_subscribe(self, interaction)

    @inventory.command(name="unsubscribe", description="Remove the live DCHS inventory status from this channel")
    @app_commands.check(admin_or_sc_bot)
    async def unsubscribe(self, interaction: discord.Interaction) -> None:
        await _handle_unsubscribe(self, interaction)

    @status_group.command(name="mine", description="Show your own DCHS inventory")
    async def status_mine(self, interaction: discord.Interaction) -> None:
        await _handle_status_mine(self, interaction)

    @status_group.command(name="everyone", description="Show all members' DCHS inventory and complete sets")
    async def status_everyone(self, interaction: discord.Interaction) -> None:
        await _handle_status_everyone(self, interaction)

    @admin_group.command(name="add", description="Add DCHS cards to a member's inventory")
    @app_commands.rename(
        dchs_01="dchs-01", dchs_02="dchs-02", dchs_03="dchs-03",
        dchs_04="dchs-04", dchs_05="dchs-05", dchs_06="dchs-06", dchs_07="dchs-07",
    )
    @app_commands.describe(
        member="The member to add cards for",
        dchs_01="Number of DCHS-01 to add", dchs_02="Number of DCHS-02 to add",
        dchs_03="Number of DCHS-03 to add", dchs_04="Number of DCHS-04 to add",
        dchs_05="Number of DCHS-05 to add", dchs_06="Number of DCHS-06 to add",
        dchs_07="Number of DCHS-07 to add",
    )
    async def admin_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        dchs_01: int | None = None, dchs_02: int | None = None, dchs_03: int | None = None,
        dchs_04: int | None = None, dchs_05: int | None = None, dchs_06: int | None = None,
        dchs_07: int | None = None,
    ) -> None:
        entries = [
            (item, count) for item, count in [
                ("DCHS-01", dchs_01), ("DCHS-02", dchs_02), ("DCHS-03", dchs_03),
                ("DCHS-04", dchs_04), ("DCHS-05", dchs_05), ("DCHS-06", dchs_06),
                ("DCHS-07", dchs_07),
            ] if count is not None
        ]
        if not entries:
            await interaction.response.send_message("Please specify at least one card.", ephemeral=True)
            return
        await _handle_admin_add(self, interaction, member, entries)

    @admin_group.command(name="remove", description="Remove DCHS cards from a member's inventory")
    @app_commands.rename(
        dchs_01="dchs-01", dchs_02="dchs-02", dchs_03="dchs-03",
        dchs_04="dchs-04", dchs_05="dchs-05", dchs_06="dchs-06", dchs_07="dchs-07",
    )
    @app_commands.describe(
        member="The member to remove cards from",
        dchs_01="Number of DCHS-01 to remove", dchs_02="Number of DCHS-02 to remove",
        dchs_03="Number of DCHS-03 to remove", dchs_04="Number of DCHS-04 to remove",
        dchs_05="Number of DCHS-05 to remove", dchs_06="Number of DCHS-06 to remove",
        dchs_07="Number of DCHS-07 to remove",
    )
    async def admin_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        dchs_01: int | None = None, dchs_02: int | None = None, dchs_03: int | None = None,
        dchs_04: int | None = None, dchs_05: int | None = None, dchs_06: int | None = None,
        dchs_07: int | None = None,
    ) -> None:
        entries = [
            (item, count) for item, count in [
                ("DCHS-01", dchs_01), ("DCHS-02", dchs_02), ("DCHS-03", dchs_03),
                ("DCHS-04", dchs_04), ("DCHS-05", dchs_05), ("DCHS-06", dchs_06),
                ("DCHS-07", dchs_07),
            ] if count is not None
        ]
        if not entries:
            await interaction.response.send_message("Please specify at least one card.", ephemeral=True)
            return
        await _handle_admin_remove(self, interaction, member, entries)

    @admin_group.command(name="clear", description="Clear all DCHS items from a member's inventory")
    @app_commands.describe(member="The member whose inventory to clear")
    async def admin_clear(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await _handle_admin_clear(self, interaction, member)

    @admin_group.command(name="clear-all", description="Clear all members' inventories")
    async def admin_clear_all(self, interaction: discord.Interaction) -> None:
        await _handle_admin_clear_all(self, interaction)

    @admin_group.command(name="transfer-set", description="Transfer one complete set from one member to another")
    @app_commands.describe(sender="The member to transfer from", recipient="The member to transfer to")
    async def admin_transfer_set(
        self,
        interaction: discord.Interaction,
        sender: discord.Member,
        recipient: discord.Member,
    ) -> None:
        await _handle_admin_transfer_set(self, interaction, sender, recipient)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InventoryCog(bot))
