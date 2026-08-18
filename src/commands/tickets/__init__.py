"""Ticket system: a panel of category buttons and slash commands that open
per-request threads, plus admin commands to configure the panel and role
pings.
"""

from __future__ import annotations

import logging
import traceback
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.checks import admin_or_sc_bot, handle_check_failure

from .lifecycle import open_ticket
from .location import location_autocomplete
from .setup_cmd import handle_role, handle_setup
from .views import PanelView, TicketView

logger = logging.getLogger(__name__)

_CategoryKey = Literal["mining", "medic", "squad", "backup", "cargo", "salvage"]


class TicketsCog(commands.Cog):
    """Panel-driven support ticket system."""

    ticket = app_commands.Group(name="ticket", description="Open and manage support tickets")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ticket_command_id: int | None = None

    async def cog_load(self) -> None:
        self.panel_view = PanelView(self)
        self.ticket_view = TicketView(self)
        self.bot.add_view(self.panel_view)
        self.bot.add_view(self.ticket_view)
        try:
            commands_ = await self.bot.tree.fetch_commands()
            for command in commands_:
                if command.name == "ticket":
                    self._ticket_command_id = command.id
                    break
        except discord.HTTPException:
            logger.warning("Could not fetch app commands to cache the /ticket command id")

    def command_mention(self, category_key: str) -> str:
        if self._ticket_command_id is not None:
            return f"</ticket {category_key}:{self._ticket_command_id}>"
        return f"`/ticket {category_key}`"

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await handle_check_failure(interaction, error)
            return
        cmd = interaction.command.qualified_name if interaction.command else "unknown"
        logger.exception("Unhandled error in ticket command: %s", error)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await interaction.client.dm_owner(f"**Error in `/{cmd}`**\n```\n{tb[:1900]}\n```")
        msg = "Something went wrong. Check the bot logs for details."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    @ticket.command(name="setup", description="Install the ticket panel in this channel")
    @app_commands.describe(channel="Channel to install the panel in (defaults to the current channel)")
    @app_commands.check(admin_or_sc_bot)
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | discord.ForumChannel | None = None,
    ) -> None:
        await handle_setup(self, interaction, channel)

    @ticket.command(name="role", description="Map a category to a responder role")
    @app_commands.describe(category="Ticket category", role="Role to ping for this category")
    @app_commands.check(admin_or_sc_bot)
    async def role(
        self,
        interaction: discord.Interaction,
        category: _CategoryKey,
        role: discord.Role,
    ) -> None:
        await handle_role(self, interaction, category, role)

    @ticket.command(name="mining", description="Request mining assistance")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        need="What you need",
        notes="Extra details",
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def mining(
        self,
        interaction: discord.Interaction,
        location: str,
        need: str | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if need:
            fields["need"] = need
        if notes:
            fields["notes"] = notes
        await open_ticket(self, interaction, "mining", fields)

    @ticket.command(name="medic", description="Request a medic")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        tier="Injury tier (T1 to T3)",
        notes="Extra details",
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def medic(
        self,
        interaction: discord.Interaction,
        location: str,
        tier: str | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if tier:
            fields["tier"] = tier
        if notes:
            fields["notes"] = notes
        await open_ticket(self, interaction, "medic", fields)

    @ticket.command(name="squad", description="Request squad/FPS backup")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        size="Squad size needed",
        notes="Extra details",
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def squad(
        self,
        interaction: discord.Interaction,
        location: str,
        size: str | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if size:
            fields["size"] = size
        if notes:
            fields["notes"] = notes
        await open_ticket(self, interaction, "squad", fields)

    @ticket.command(name="backup", description="Request backup, you are under attack")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        threat="What is attacking you",
        urgency="How urgent this is",
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def backup(
        self,
        interaction: discord.Interaction,
        location: str,
        threat: str | None = None,
        urgency: str | None = None,
    ) -> None:
        fields = {"location": location}
        if threat:
            fields["threat"] = threat
        if urgency:
            fields["urgency"] = urgency
        await open_ticket(self, interaction, "backup", fields)

    @ticket.command(name="cargo", description="Request cargo hauling help")
    @app_commands.rename(route_from="route-from", route_to="route-to")
    @app_commands.describe(
        route_from="Pickup (system:planet:location)",
        route_to="Destination (system:planet:location)",
        scu="Cargo size in SCU",
        notes="Extra details",
    )
    @app_commands.autocomplete(route_from=location_autocomplete, route_to=location_autocomplete)
    async def cargo(
        self,
        interaction: discord.Interaction,
        route_from: str,
        route_to: str,
        scu: str | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"route_from": route_from, "route_to": route_to}
        if scu:
            fields["scu"] = scu
        if notes:
            fields["notes"] = notes
        await open_ticket(self, interaction, "cargo", fields)

    @ticket.command(name="salvage", description="Request salvage assistance")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        target="Salvage target",
        notes="Extra details",
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def salvage(
        self,
        interaction: discord.Interaction,
        location: str,
        target: str | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if target:
            fields["target"] = target
        if notes:
            fields["notes"] = notes
        await open_ticket(self, interaction, "salvage", fields)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
