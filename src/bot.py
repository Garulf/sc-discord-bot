"""The bot core: a :class:`commands.Bot` subclass that owns shared resources
and wires up command extensions. Command logic itself lives in the cogs under
``src/commands``."""

from __future__ import annotations

import logging
import os
import time
import traceback

import discord
from discord.ext import commands

from src.starcitizenwiki_api import (
    Armor,
    Clothes,
    Items,
    Ships,
    ShipWeapons,
    StarCitizenWikiClient,
    VehicleItems,
    WeaponAttachments,
    Weapons,
)
from src.starcitizenwiki_api.blueprints import Blueprints
from src.starcitizenwiki_api.celestial_objects import CelestialObjects
from src.starcitizenwiki_api.comm_links import CommLinks
from src.starcitizenwiki_api.factions import Factions
from src.starcitizenwiki_api.food import Food
from src.starcitizenwiki_api.galactapedia import Galactapedia
from src.starcitizenwiki_api.game_versions import GameVersions
from src.starcitizenwiki_api.gravlev_vehicles import GravlevVehicles
from src.starcitizenwiki_api.ground_vehicles import GroundVehicles
from src.starcitizenwiki_api.locations import Locations
from src.starcitizenwiki_api.manufacturers import Manufacturers
from src.starcitizenwiki_api.mineables import Mineables
from src.starcitizenwiki_api.missions import Missions
from src.starcitizenwiki_api.starsystems import StarSystems
from src.starcitizenwiki_api.stats import Stats
from src.starcitizenwiki_api.wiki_commodities import WikiCommodities
from src.storage import Database, SqliteCache, StateStore
from src.uex_api import (
    Commodities,
    CommodityPrices,
    Terminals,
    UEXClient,
    VehiclePrices,
    Vehicles,
)

DEFAULT_DB_PATH = "data/bot.db"

logger = logging.getLogger(__name__)

# Cogs to load on startup. Each module exposes an async ``setup(bot)``.
INITIAL_EXTENSIONS = [
    "src.commands.hangar",
    "src.commands.ships",
    "src.commands.shipprice",
    "src.commands.commodity",
    "src.commands.status",
    "src.commands.find",
    "src.commands.inventory",
    "src.commands.timer",
    "src.commands.mine",
]


class SCBot(commands.Bot):
    """Star Citizen helper bot.

    Holds the shared Star Citizen Wiki API client so every cog can reuse a
    single HTTP session, and handles one-time setup (loading cogs, syncing
    slash commands) plus clean shutdown.
    """

    def __init__(self) -> None:
        intents = discord.Intents.default()
        # This bot only uses slash commands, but discord.py still runs every
        # message through get_prefix(); a None prefix raises there. Respond only
        # to @-mentions for the (unused) prefix command path.
        super().__init__(command_prefix=commands.when_mentioned, intents=intents, help_command=None)

        # Shared SQLite store for persistent API caching and bot state. The
        # connection is opened in :meth:`setup_hook` once the loop is running.
        self.db = Database(os.getenv("DB_PATH", DEFAULT_DB_PATH))
        self.state = StateStore(self.db)

        # Shared API clients. HTTP sessions are created lazily on first use so
        # they bind to the running event loop; closed again in :meth:`close`.
        self.sc_client = StarCitizenWikiClient(locale="en_EN", cache=SqliteCache(self.db, namespace="wiki"))
        self.ships_api = Ships(self.sc_client)
        self.weapons_api = Weapons(self.sc_client)
        self.ship_weapons_api = ShipWeapons(self.sc_client)
        self.armor_api = Armor(self.sc_client)
        self.clothes_api = Clothes(self.sc_client)
        self.vehicle_items_api = VehicleItems(self.sc_client)
        self.weapon_attachments_api = WeaponAttachments(self.sc_client)
        self.items_api = Items(self.sc_client)
        self.blueprints_api = Blueprints(self.sc_client)
        self.missions_api = Missions(self.sc_client)
        self.celestial_objects_api = CelestialObjects(self.sc_client)
        self.starsystems_api = StarSystems(self.sc_client)
        self.locations_api = Locations(self.sc_client)
        self.ground_vehicles_api = GroundVehicles(self.sc_client)
        self.gravlev_vehicles_api = GravlevVehicles(self.sc_client)
        self.factions_api = Factions(self.sc_client)
        self.manufacturers_api = Manufacturers(self.sc_client)
        self.wiki_commodities_api = WikiCommodities(self.sc_client)
        self.mineables_api = Mineables(self.sc_client)
        self.food_api = Food(self.sc_client)
        self.galactapedia_api = Galactapedia(self.sc_client)
        self.comm_links_api = CommLinks(self.sc_client)
        self.game_versions_api = GameVersions(self.sc_client)
        self.stats_api = Stats(self.sc_client)

        self.uex_client = UEXClient(token=os.getenv("UEX_BEARER_TOKEN"), cache=SqliteCache(self.db, namespace="uex"))
        self.commodities_api = Commodities(self.uex_client)
        self.terminals_api = Terminals(self.uex_client)
        self.commodity_prices_api = CommodityPrices(self.uex_client)
        self.vehicles_api = Vehicles(self.uex_client)
        self.vehicle_prices_api = VehiclePrices(self.uex_client)

    async def setup_hook(self) -> None:
        await self.db.connect()
        for extension in INITIAL_EXTENSIONS:
            await self.load_extension(extension)
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d command(s)", len(synced))
        except Exception:  # noqa: BLE001 - log and keep running
            logger.exception("Failed to sync commands")

        @self.tree.error
        async def on_tree_error(
            interaction: discord.Interaction,
            error: discord.app_commands.AppCommandError,
        ) -> None:
            cmd = interaction.command.qualified_name if interaction.command else "unknown"
            logger.exception("Unhandled app command error in /%s: %s", cmd, error)
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            await self.dm_owner(f"**Error in `/{cmd}`**\n```\n{tb[:1900]}\n```")
            msg = "Something went wrong. Check the bot logs for details."
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass

    _dm_cooldown_until: float = 0.0
    _DM_COOLDOWN = 60.0

    async def dm_owner(self, content: str) -> None:
        now = time.monotonic()
        if now < self._dm_cooldown_until:
            return
        self._dm_cooldown_until = now + self._DM_COOLDOWN
        try:
            info = await self.application_info()
            await info.owner.send(content)
        except Exception:
            logger.exception("Failed to DM owner")

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user.name if self.user else "?")

    async def on_app_command_completion(
        self, interaction: discord.Interaction, command: discord.app_commands.Command | discord.app_commands.ContextMenu
    ) -> None:
        guild = interaction.guild.name if interaction.guild else "DM"
        params = {k: v for k, v in interaction.namespace.__dict__.items() if v is not None}
        logger.info(
            "Command /%s completed — user=%s guild=%s params=%s",
            command.qualified_name,
            interaction.user,
            guild,
            params,
        )

    async def close(self) -> None:
        await self.sc_client.close()
        await self.uex_client.close()
        await self.db.close()
        await super().close()
