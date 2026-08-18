"""Beacon system: a panel of category buttons and slash commands that open
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

from . import store
from .categories import CATEGORIES, CONTESTED_STATIONS
from .lifecycle import handle_again, handle_close_command, handle_thread_message, open_beacon
from .location import location_autocomplete
from .setup_cmd import handle_config, handle_role, handle_setup
from .views import BeaconView, CommendView

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
        await self.refresh_command_mentions()

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
        notes="Extra details",
    )
    @app_commands.autocomplete(location=location_autocomplete)
    async def mining(
        self,
        interaction: discord.Interaction,
        location: str,
        need: Literal["Extra mining ship", "Refining help", "Escort", "Equipment"] | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if need:
            fields["need"] = need
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "mining", fields)

    @beacon.command(name="medic", description="Request a medic")
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
        tier: Literal["T1", "T2", "T3"] | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if tier:
            fields["tier"] = tier
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "medic", fields)

    @beacon.command(name="squad", description="Request squad/FPS backup")
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
        size: app_commands.Range[int, 1, 50] | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if size:
            fields["size"] = str(size)
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "squad", fields)

    @beacon.command(name="backup", description="Request backup, you are under attack")
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
        threat: Literal["Players", "NPCs", "Mixed", "Unknown"] | None = None,
        urgency: Literal["Low", "Medium", "High", "Critical"] | None = None,
    ) -> None:
        fields = {"location": location}
        if threat:
            fields["threat"] = threat
        if urgency:
            fields["urgency"] = urgency
        await open_beacon(self, interaction, "backup", fields)

    @beacon.command(name="cargo", description="Request cargo hauling help")
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
        scu: app_commands.Range[int, 1, 100000] | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"route_from": route_from, "route_to": route_to}
        if scu:
            fields["scu"] = str(scu)
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "cargo", fields)

    @beacon.command(name="salvage", description="Request salvage assistance")
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
        target: Literal["Ship wreck", "Panels", "Structure", "Unknown"] | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if target:
            fields["target"] = target
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "salvage", fields)

    @beacon.command(name="escort", description="Request a ship escort")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        destination="Where you are headed (system:planet:location)",
        notes="Extra details",
    )
    @app_commands.autocomplete(location=location_autocomplete, destination=location_autocomplete)
    async def escort(
        self,
        interaction: discord.Interaction,
        location: str,
        destination: str | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if destination:
            fields["destination"] = destination
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "escort", fields)

    @beacon.command(name="transport", description="Request personal transport")
    @app_commands.describe(
        location="Where you are (system:planet:location)",
        destination="Where you want to go (system:planet:location)",
        notes="Extra details",
    )
    @app_commands.autocomplete(location=location_autocomplete, destination=location_autocomplete)
    async def transport(
        self,
        interaction: discord.Interaction,
        location: str,
        destination: str | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": location}
        if destination:
            fields["destination"] = destination
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "transport", fields)

    @beacon.command(name="contested", description="Group up to run a contested zone")
    @app_commands.describe(
        location="Contested zone station",
        objective="What you want to do there",
        size="Group size needed",
        notes="Extra details",
    )
    @app_commands.choices(location=[app_commands.Choice(name=s, value=s) for s in CONTESTED_STATIONS])
    async def contested(
        self,
        interaction: discord.Interaction,
        location: str,
        objective: Literal["Vault run", "Full clear", "Keycard run", "Extraction help"] | None = None,
        size: app_commands.Range[int, 1, 50] | None = None,
        notes: str | None = None,
    ) -> None:
        fields = {"location": f"Pyro:{location}"}
        if objective:
            fields["objective"] = objective
        if size:
            fields["size"] = str(size)
        if notes:
            fields["notes"] = notes
        await open_beacon(self, interaction, "contested", fields)

    @beacon.command(name="close", description="Close this beacon")
    async def close(self, interaction: discord.Interaction) -> None:
        await handle_close_command(self, interaction)

    @beacon.command(name="again", description="Repeat your last beacon")
    async def again(self, interaction: discord.Interaction) -> None:
        await handle_again(self, interaction)

    @beacon.command(name="config", description="View or change beacon settings")
    @app_commands.describe(
        idle_warn="Minutes idle before a warning (5-1440)",
        idle_close="Minutes idle before auto-closing (5-1440)",
        escalate="Minutes after the warning before escalating (1-1440)",
        voice="Auto-create a voice channel when a beacon fills",
        digest_channel="Channel to post the weekly digest in",
        clear_digest="Unset the digest channel",
    )
    @app_commands.check(admin_or_sc_bot)
    async def config(
        self,
        interaction: discord.Interaction,
        idle_warn: app_commands.Range[int, 5, 1440] | None = None,
        idle_close: app_commands.Range[int, 5, 1440] | None = None,
        escalate: app_commands.Range[int, 1, 1440] | None = None,
        voice: bool | None = None,
        digest_channel: discord.TextChannel | None = None,
        clear_digest: bool | None = None,
    ) -> None:
        await handle_config(
            self,
            interaction,
            idle_warn=idle_warn,
            idle_close=idle_close,
            escalate=escalate,
            voice=voice,
            digest_channel=digest_channel,
            clear_digest=clear_digest,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BeaconsCog(bot))
