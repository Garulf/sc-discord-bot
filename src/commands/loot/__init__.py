"""Raid loot tracking: log cargo against a beacon or a standalone raid, record
sales, and split each sale equally among the crew."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.checks import admin_or_sc_bot, handle_check_failure
from src.commands.commodity.shared import autocomplete_commodity

from . import handlers
from .ledger import MAX_SCU
from .views import LogLootView, LootCardView

_MAX_AUEC = 1_000_000_000_000


class LootCog(commands.Cog):
    """Raid loot tracking and equal-share sale splits."""

    loot = app_commands.Group(name="loot", description="Track raid loot and split sales", guild_only=True)
    participants = app_commands.Group(name="participants", description="Change who shares in a raid", parent=loot)
    cargo = app_commands.Group(name="cargo", description="Correct a raid's cargo", parent=loot)
    config = app_commands.Group(name="config", description="Loot settings", parent=loot)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.card_view = LootCardView(self)
        self.bot.add_view(self.card_view)
        self.log_view = LogLootView(self)
        self.bot.add_view(self.log_view)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handle_check_failure(interaction, error)

    async def _raid_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await handlers.raid_autocomplete(self, interaction, current)

    async def _cargo_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await handlers.cargo_autocomplete(self, interaction, current)

    async def _commodity_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await autocomplete_commodity(self, current)

    @loot.command(name="new", description="Start tracking loot from a raid with no beacon")
    @app_commands.describe(
        title="What the raid was, e.g. Ruin gold grab",
        commodity="What you took",
        scu="How much",
        participants="Crew to include, as @mentions (you're always included)",
        holder="Who is holding the cargo (default: you)",
    )
    @app_commands.autocomplete(commodity=_commodity_ac)
    async def new(
        self,
        interaction: discord.Interaction,
        title: app_commands.Range[str, 1, 100],
        commodity: app_commands.Range[str, 1, 100],
        scu: app_commands.Range[int, 1, MAX_SCU],
        participants: str | None = None,
        holder: discord.Member | None = None,
    ) -> None:
        await handlers.handle_new(
            self,
            interaction,
            title=title,
            commodity=commodity,
            scu=scu,
            participants=participants,
            holder_id=holder.id if holder else None,
        )

    @loot.command(name="log", description="Log loot on this beacon, or add cargo to a raid")
    @app_commands.describe(
        commodity="What you took",
        scu="How much",
        holder="Who is holding it (default: you)",
        raid="Add to this raid instead of the current beacon",
    )
    @app_commands.autocomplete(commodity=_commodity_ac, raid=_raid_ac)
    async def log(
        self,
        interaction: discord.Interaction,
        commodity: app_commands.Range[str, 1, 100],
        scu: app_commands.Range[int, 1, MAX_SCU],
        holder: discord.Member | None = None,
        raid: str | None = None,
    ) -> None:
        await handlers.handle_log(
            self,
            interaction,
            commodity=commodity,
            scu=scu,
            holder_id=holder.id if holder else interaction.user.id,
            raid=raid,
        )

    @loot.command(name="sell", description="Record a sale and split it with the crew")
    @app_commands.describe(raid="Raid", commodity="What you sold", scu="How much you sold", total="aUEC received")
    @app_commands.autocomplete(raid=_raid_ac, commodity=_cargo_ac)
    async def sell(
        self,
        interaction: discord.Interaction,
        raid: str,
        commodity: str,
        scu: app_commands.Range[int, 1, MAX_SCU],
        total: app_commands.Range[int, 1, _MAX_AUEC],
    ) -> None:
        await handlers.handle_sell(self, interaction, raid=raid, commodity=commodity, scu=scu, total=total)

    @loot.command(name="paid", description="Mark a share as paid (leave member empty for everyone you owe)")
    @app_commands.describe(raid="Raid", member="Who you paid")
    @app_commands.autocomplete(raid=_raid_ac)
    async def paid(self, interaction: discord.Interaction, raid: str, member: discord.Member | None = None) -> None:
        await handlers.handle_paid(self, interaction, raid=raid, member_id=member.id if member else None)

    @loot.command(name="dispute", description="Flag a share marked paid that you never received")
    @app_commands.describe(raid="Raid")
    @app_commands.autocomplete(raid=_raid_ac)
    async def dispute(self, interaction: discord.Interaction, raid: str) -> None:
        await handlers.handle_dispute(self, interaction, raid=raid)

    @loot.command(name="undo", description="Remove the most recent sale on a raid")
    @app_commands.describe(raid="Raid")
    @app_commands.autocomplete(raid=_raid_ac)
    async def undo(self, interaction: discord.Interaction, raid: str) -> None:
        await handlers.handle_undo(self, interaction, raid=raid)

    @loot.command(name="holder", description="Hand cargo to another member")
    @app_commands.describe(raid="Raid", commodity="Cargo to hand over", member="New holder")
    @app_commands.autocomplete(raid=_raid_ac, commodity=_cargo_ac)
    async def holder(self, interaction: discord.Interaction, raid: str, commodity: str, member: discord.Member) -> None:
        await handlers.handle_holder(self, interaction, raid=raid, commodity=commodity, member_id=member.id)

    @loot.command(name="delete", description="Delete a raid with nothing owed")
    @app_commands.describe(raid="Raid")
    @app_commands.autocomplete(raid=_raid_ac)
    @app_commands.check(admin_or_sc_bot)
    async def delete(self, interaction: discord.Interaction, raid: str) -> None:
        await handlers.handle_delete(self, interaction, raid=raid)

    @loot.command(name="owed", description="What you're owed, what you owe, and what you hold")
    async def owed(self, interaction: discord.Interaction) -> None:
        await handlers.handle_owed(self, interaction)

    @loot.command(name="list", description="Raids that aren't settled yet")
    async def list_raids(self, interaction: discord.Interaction) -> None:
        await handlers.handle_list(self, interaction)

    @participants.command(name="add", description="Add someone to a raid's crew")
    @app_commands.describe(raid="Raid", member="Member to add")
    @app_commands.autocomplete(raid=_raid_ac)
    async def participants_add(self, interaction: discord.Interaction, raid: str, member: discord.Member) -> None:
        await handlers.handle_participants(self, interaction, raid=raid, action="add", member_id=member.id)

    @participants.command(name="remove", description="Remove someone from a raid's crew")
    @app_commands.describe(raid="Raid", member="Member to remove")
    @app_commands.autocomplete(raid=_raid_ac)
    async def participants_remove(self, interaction: discord.Interaction, raid: str, member: discord.Member) -> None:
        await handlers.handle_participants(self, interaction, raid=raid, action="remove", member_id=member.id)

    @cargo.command(name="fix", description="Correct how much of a commodity a raid took")
    @app_commands.describe(raid="Raid", commodity="Cargo to correct", scu="Correct total SCU (0 removes it)")
    @app_commands.autocomplete(raid=_raid_ac, commodity=_cargo_ac)
    async def cargo_fix(
        self,
        interaction: discord.Interaction,
        raid: str,
        commodity: str,
        scu: app_commands.Range[int, 0, MAX_SCU],
    ) -> None:
        await handlers.handle_cargo_fix(self, interaction, raid=raid, commodity=commodity, scu=scu)

    @config.command(name="channel", description="Post loot cards in this channel")
    @app_commands.describe(channel="Channel for loot cards")
    @app_commands.check(admin_or_sc_bot)
    async def config_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await handlers.handle_config_channel(self, interaction, channel)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LootCog(bot))
