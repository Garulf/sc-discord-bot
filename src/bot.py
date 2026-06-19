"""The bot core: a :class:`commands.Bot` subclass that owns shared resources
and wires up command extensions. Command logic itself lives in the cogs under
``src/commands``."""

from __future__ import annotations

import logging
import os

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
from src.starcitizenwiki_api.missions import Missions
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

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user.name if self.user else "?")

    async def close(self) -> None:
        await self.sc_client.close()
        await self.uex_client.close()
        await self.db.close()
        await super().close()
