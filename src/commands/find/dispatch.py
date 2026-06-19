"""Dispatch table for /find subcommands — maps category keys to API attrs and
embed builders. Subcommand files import nothing from here; the Cog's
``_handle_single`` method uses DISPATCH to route lookups."""

from __future__ import annotations

from .armor import build_armor_embed
from .clothes import build_clothes_embed
from .item import build_item_embed
from .shipweapon import build_ship_weapon_embed
from .vehicleitem import build_vehicle_item_embed
from .weapon import build_weapon_embed
from .weaponattachment import build_weapon_attachment_embed

DISPATCH = {
    "weapon": ("weapons_api", build_weapon_embed),
    "ship-weapon": ("ship_weapons_api", build_ship_weapon_embed),
    "armor": ("armor_api", build_armor_embed),
    "clothes": ("clothes_api", build_clothes_embed),
    "vehicle-item": ("vehicle_items_api", build_vehicle_item_embed),
    "weapon-attachment": ("weapon_attachments_api", build_weapon_attachment_embed),
    "item": ("items_api", build_item_embed),
}

CATEGORIES = [
    ("weapon", "Weapon"),
    ("ship-weapon", "Ship Weapon"),
    ("armor", "Armor"),
    ("clothes", "Clothing"),
    ("vehicle-item", "Vehicle Item"),
    ("weapon-attachment", "Weapon Attachment"),
    ("item", "Item"),
]

API_ATTRS = [
    "weapons_api",
    "ship_weapons_api",
    "armor_api",
    "clothes_api",
    "vehicle_items_api",
    "weapon_attachments_api",
    "items_api",
]
