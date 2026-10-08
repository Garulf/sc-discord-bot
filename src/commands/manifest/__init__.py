"""Manifests: one haul's cargo, costs, crew and carrier, with each sale's
proceeds paying back costs first and then split by crew weight."""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.commands.checks import admin_or_sc_bot, handle_check_failure

from . import handlers, store
from .views import CreateFromBeaconView, ManifestCardView

logger = logging.getLogger(__name__)


class ManifestCog(commands.Cog):
    """Cargo manifests with weighted profit shares."""

    manifest = app_commands.Group(
        name="manifest", description="Track a haul's cargo, costs and crew shares", guild_only=True
    )
    config = app_commands.Group(name="config", description="Manifest settings", parent=manifest)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.card_view = ManifestCardView(self)
        self.bot.add_view(self.card_view)
        self.log_view = CreateFromBeaconView(self)
        self.bot.add_view(self.log_view)
        purged = await store.purge_legacy_loot(self.bot.state)
        if purged:
            logger.info("Removed %s legacy loot entries", purged)

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        await handle_check_failure(interaction, error)

    async def _manifest_ac(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await handlers.manifest_autocomplete(self, interaction, current)

    @manifest.command(name="new", description="Start a manifest for a haul")
    async def new(self, interaction: discord.Interaction) -> None:
        await handlers.handle_new(self, interaction)

    @manifest.command(name="list", description="Your manifests, with open cargo value and overall profit")
    async def list_manifests(self, interaction: discord.Interaction) -> None:
        await handlers.handle_list(self, interaction)

    @manifest.command(name="owed", description="What you're owed, what you owe, and what you're carrying")
    async def owed(self, interaction: discord.Interaction) -> None:
        await handlers.handle_owed(self, interaction)

    @manifest.command(name="delete", description="Delete a manifest with nothing owed")
    @app_commands.describe(manifest="Manifest")
    @app_commands.autocomplete(manifest=_manifest_ac)
    @app_commands.check(admin_or_sc_bot)
    async def delete(self, interaction: discord.Interaction, manifest: str) -> None:
        await handlers.handle_delete(self, interaction, manifest)

    @config.command(name="channel", description="Create manifest threads in this channel")
    @app_commands.describe(channel="Channel for manifest threads")
    @app_commands.check(admin_or_sc_bot)
    async def config_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await handlers.handle_config_channel(self, interaction, channel)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ManifestCog(bot))
