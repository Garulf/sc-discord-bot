"""Beacon system: a panel of category buttons and slash commands that open
per-request threads, plus admin commands to configure the panel and role
pings.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands, tasks

from src.commands.checks import admin_or_sc_bot, handle_check_failure

from . import scheduled, setup_cmd, store
from .board import handle_board
from .categories import CATEGORIES, CONTESTED_STATIONS
from .lifecycle import handle_again, handle_close_command, handle_thread_message
from .location import location_autocomplete
from .maintenance import run_maintenance
from .setup_cmd import handle_role, handle_setup
from .stats import handle_stats
from .views import BeaconView, CommendView, ScheduledBeaconView

logger = logging.getLogger(__name__)

_CATEGORY_CHOICES = [app_commands.Choice(name=category.label, value=category.key) for category in CATEGORIES.values()]


class BeaconsCog(commands.Cog):
    """Panel-driven support beacon system."""

    beacon = app_commands.Group(name="beacon", description="Open and manage support beacons", guild_only=True)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._beacon_command_id: int | None = None

    async def cog_load(self) -> None:
        await store.migrate_legacy_keys(self.bot.state)
        await self._warn_stale_configs()
        self.beacon_view = BeaconView(self)
        self.bot.add_view(self.beacon_view)
        self.bot.add_view(BeaconView(self, legacy=True))
        self.bot.add_view(CommendView(self))
        self.scheduled_beacon_view = ScheduledBeaconView(self)
        self.bot.add_view(self.scheduled_beacon_view)
        await self.refresh_command_mentions()
        self.maintenance_loop.start()

    async def cog_unload(self) -> None:
        self.maintenance_loop.cancel()

    @tasks.loop(minutes=5)
    async def maintenance_loop(self) -> None:
        for guild in self.bot.guilds:
            try:
                await run_maintenance(self, guild, time.time())
            except Exception:
                logger.exception("Beacon maintenance loop failed for guild %s", guild.id)

    @maintenance_loop.before_loop
    async def before_maintenance_loop(self) -> None:
        await self.bot.wait_until_ready()

    @maintenance_loop.error
    async def maintenance_loop_error(self, error: Exception) -> None:
        logger.exception("Beacon maintenance loop error: %s", error)

    async def refresh_command_mentions(self) -> None:
        try:
            commands_ = await self.bot.tree.fetch_commands()
            for command in commands_:
                if command.name == "beacon":
                    self._beacon_command_id = command.id
                    break
        except discord.HTTPException:
            logger.warning("Could not fetch app commands to cache the /beacon command id")

    async def _warn_stale_configs(self) -> None:
        for key in await self.bot.state.keys("beacons:config:"):
            config = await self.bot.state.get(key)
            missing = set(CATEGORIES) - set((config or {}).get("tag_ids", {}) or CATEGORIES)
            if missing:
                logger.warning(
                    "Beacon config %s lacks forum tags for %s; re-run /beacon setup to refresh them",
                    key,
                    ", ".join(sorted(missing)),
                )

    def command_mention(self, category_key: str) -> str:
        if self._beacon_command_id is not None:
            return f"</beacon {category_key}:{self._beacon_command_id}>"
        return f"`/beacon {category_key}`"

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message) -> None:
        await handle_thread_message(self, message)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await handle_check_failure(interaction, error)
            return
        cmd = interaction.command.qualified_name if interaction.command else "unknown"
        logger.exception("Unhandled error in beacon command: %s", error)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await interaction.client.dm_owner(f"**Error in `/{cmd}`**\n```\n{tb[:1900]}\n```")
        msg = "Something went wrong. Check the bot logs for details."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    @beacon.command(name="setup", description="Install the beacon panel in this channel")
    @app_commands.describe(channel="Channel to install the panel in (defaults to the current channel)")
    @app_commands.check(admin_or_sc_bot)
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | discord.ForumChannel | None = None,
    ) -> None:
        await handle_setup(self, interaction, channel)

    @beacon.command(name="role", description="Map a category to a responder role")
    @app_commands.describe(category="Beacon category", role="Role to ping for this category")
    @app_commands.choices(category=_CATEGORY_CHOICES)
    @app_commands.check(admin_or_sc_bot)
    async def role(
        self,
        interaction: discord.Interaction,
        category: str,
        role: discord.Role,
    ) -> None:
        await handle_role(self, interaction, category, role)

    @beacon.command(name="mining", description="Request mining assistance")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        need="What you need",
        crew="Crew members needed",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def mining(
        self,
        interaction: discord.Interaction,
        location: str,
        need: Literal["Extra mining ship", "Refining help", "Escort", "Equipment"] | None = None,
        crew: app_commands.Range[int, 1, 50] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if need:
            fields["need"] = need
        if crew:
            fields["size"] = str(crew)
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "mining", fields, when)

    @beacon.command(name="medic", description="Request a medic")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        tier="Injury tier (T1 to T3)",
        danger="Danger level",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def medic(
        self,
        interaction: discord.Interaction,
        location: str,
        tier: Literal["T1", "T2", "T3"] | None = None,
        danger: Literal["Unknown", "None", "Low", "Medium", "High"] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if tier:
            fields["tier"] = tier
        if danger:
            fields["danger"] = danger
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "medic", fields, when)

    @beacon.command(name="squad", description="Request squad/FPS backup")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        size="Squad size needed",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def squad(
        self,
        interaction: discord.Interaction,
        location: str,
        size: app_commands.Range[int, 1, 50] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if size:
            fields["size"] = str(size)
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "squad", fields, when)

    @beacon.command(name="backup", description="Request backup, you are under attack")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        threat="What is attacking you",
        urgency="How urgent this is",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def backup(
        self,
        interaction: discord.Interaction,
        location: str,
        threat: Literal["Players", "NPCs", "Mixed", "Unknown"] | None = None,
        urgency: Literal["Low", "Medium", "High", "Critical"] | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if threat:
            fields["threat"] = threat
        if urgency:
            fields["urgency"] = urgency
        await scheduled.open_or_schedule(self, interaction, "backup", fields, when)

    @beacon.command(name="cargo", description="Request cargo hauling help")
    @app_commands.rename(route_from="route-from", route_to="route-to")
    @app_commands.describe(
        route_from="Pickup (system:planet:location)",
        route_to="Destination (system:planet:location)",
        scu="Cargo size in SCU",
        danger="Danger level",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(route_from=location_autocomplete, route_to=location_autocomplete)
    async def cargo(
        self,
        interaction: discord.Interaction,
        route_from: str,
        route_to: str,
        scu: app_commands.Range[int, 1, 100000] | None = None,
        danger: Literal["Unknown", "None", "Low", "Medium", "High"] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"route_from": route_from, "route_to": route_to}
        if scu:
            fields["scu"] = str(scu)
        if danger:
            fields["danger"] = danger
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "cargo", fields, when)

    @beacon.command(name="salvage", description="Request salvage assistance")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        target="Salvage target",
        crew="Crew members needed",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def salvage(
        self,
        interaction: discord.Interaction,
        location: str,
        target: Literal["Ship wreck", "Panels", "Structure", "Unknown"] | None = None,
        crew: app_commands.Range[int, 1, 50] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if target:
            fields["target"] = target
        if crew:
            fields["size"] = str(crew)
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "salvage", fields, when)

    @beacon.command(name="escort", description="Request a ship escort")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        destination="Where you are headed (system:planet:location)",
        danger="Danger level",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete, destination=location_autocomplete)
    async def escort(
        self,
        interaction: discord.Interaction,
        location: str,
        destination: str | None = None,
        danger: Literal["Unknown", "None", "Low", "Medium", "High"] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if destination:
            fields["destination"] = destination
        if danger:
            fields["danger"] = danger
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "escort", fields, when)

    @beacon.command(name="transport", description="Request personal transport")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        destination="Where you want to go (system:planet:location)",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.autocomplete(location=location_autocomplete, destination=location_autocomplete)
    async def transport(
        self,
        interaction: discord.Interaction,
        location: str,
        destination: str | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": location}
        if destination:
            fields["destination"] = destination
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "transport", fields, when)

    @beacon.command(name="contested", description="Group up to run a contested zone")
    @app_commands.describe(
        location="Contested zone station",
        objective="What you want to do there",
        size="Group size needed",
        notes="Extra details",
        when='Schedule this beacon instead of opening it now (e.g. "45m", "2h")',
    )
    @app_commands.choices(location=[app_commands.Choice(name=s, value=s) for s in CONTESTED_STATIONS])
    async def contested(
        self,
        interaction: discord.Interaction,
        location: str,
        objective: Literal["Vault run", "Full clear", "Keycard run", "Extraction help"] | None = None,
        size: app_commands.Range[int, 1, 50] | None = None,
        notes: str | None = None,
        when: str | None = None,
    ) -> None:
        fields = {"location": f"Pyro:{location}"}
        if objective:
            fields["objective"] = objective
        if size:
            fields["size"] = str(size)
        if notes:
            fields["notes"] = notes
        await scheduled.open_or_schedule(self, interaction, "contested", fields, when)

    @beacon.command(name="close", description="Close this beacon")
    async def close(self, interaction: discord.Interaction) -> None:
        await handle_close_command(self, interaction)

    @beacon.command(name="again", description="Repeat your last beacon")
    async def again(self, interaction: discord.Interaction) -> None:
        await handle_again(self, interaction)

    @beacon.command(name="stats", description="Beacon statistics for this server")
    async def stats(self, interaction: discord.Interaction) -> None:
        await handle_stats(self, interaction)

    @beacon.command(name="board", description="Install or remove the live beacon status board")
    @app_commands.describe(action="Install or remove the board")
    @app_commands.check(admin_or_sc_bot)
    async def board(
        self,
        interaction: discord.Interaction,
        action: Literal["install", "remove"] = "install",
    ) -> None:
        await handle_board(self, interaction, action)

    @beacon.command(name="config", description="View or change beacon settings")
    @app_commands.rename(
        voice_category="voice-category", schedule_role="schedule-role", clear_schedule_role="clear-schedule-role"
    )
    @app_commands.describe(
        idle_warn="Minutes idle before a warning (5-1440)",
        idle_close="Minutes idle before auto-closing (5-1440)",
        escalate="Minutes with no responders before pinging the category role (1-1440)",
        voice="Auto-create a voice channel when a beacon fills",
        voice_category="Discord category to create voice channels in",
        digest_channel="Channel to post the weekly digest in",
        clear_digest="Unset the digest channel",
        schedule_role="Role required to schedule a beacon (unset means everyone can)",
        clear_schedule_role="Unset the schedule role, opening scheduling to everyone",
    )
    @app_commands.check(admin_or_sc_bot)
    async def config(
        self,
        interaction: discord.Interaction,
        idle_warn: app_commands.Range[int, 5, 1440] | None = None,
        idle_close: app_commands.Range[int, 5, 1440] | None = None,
        escalate: app_commands.Range[int, 1, 1440] | None = None,
        voice: bool | None = None,
        voice_category: discord.CategoryChannel | None = None,
        digest_channel: discord.TextChannel | None = None,
        clear_digest: bool | None = None,
        schedule_role: discord.Role | None = None,
        clear_schedule_role: bool | None = None,
    ) -> None:
        await setup_cmd.handle_config(
            self,
            interaction,
            idle_warn=idle_warn,
            idle_close=idle_close,
            escalate=escalate,
            voice=voice,
            voice_category=voice_category,
            digest_channel=digest_channel,
            clear_digest=clear_digest,
            schedule_role=schedule_role,
            clear_schedule_role=clear_schedule_role,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BeaconsCog(bot))
