"""Beacon category definitions: labels, emoji, and per-category form fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    required: bool = False
    kind: str = "text"
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    emoji: str
    description: str
    fields: tuple[FieldSpec, ...]


def short_label(category: Category) -> str:
    """The category label without a trailing parenthetical, safe for Discord's
    20-character forum tag name limit."""
    return category.label.split(" (")[0]


def _location() -> FieldSpec:
    return FieldSpec("location", "Location", required=True, kind="location")


def _notes() -> FieldSpec:
    return FieldSpec("notes", "Notes")


CATEGORIES: dict[str, Category] = {
    "mining": Category(
        key="mining",
        description="Mining ops support: extra ships, refining, or an escort",
        label="Mining",
        emoji="\N{PICK}",
        fields=(
            _location(),
            FieldSpec(
                "need",
                "What do you need?",
                kind="choice",
                choices=("Extra mining ship", "Refining help", "Escort", "Equipment"),
            ),
            _notes(),
        ),
    ),
    "medic": Category(
        key="medic",
        description="Rescue and revival for injured players",
        label="Medical",
        emoji="\N{ADHESIVE BANDAGE}",
        fields=(
            _location(),
            FieldSpec("tier", "Injury tier", kind="choice", choices=("T1", "T2", "T3")),
            _notes(),
        ),
    ),
    "squad": Category(
        key="squad",
        description="Fill out a squad for FPS missions",
        label="Squad/FPS",
        emoji="\N{CROSSED SWORDS}",
        fields=(
            _location(),
            FieldSpec("size", "Squad size needed", kind="int"),
            _notes(),
        ),
    ),
    "backup": Category(
        key="backup",
        description="Emergency combat assistance when you are under attack",
        label="Combat Backup",
        emoji="\N{POLICE CARS REVOLVING LIGHT}",
        fields=(
            _location(),
            FieldSpec("threat", "Threat", kind="choice", choices=("Players", "NPCs", "Mixed", "Unknown")),
            FieldSpec("urgency", "Urgency", kind="choice", choices=("Low", "Medium", "High", "Critical")),
        ),
    ),
    "cargo": Category(
        key="cargo",
        description="Hauling help for cargo routes",
        label="Cargo",
        emoji="\N{PACKAGE}",
        fields=(
            FieldSpec("route_from", "Route from", required=True, kind="route"),
            FieldSpec("route_to", "Route to", required=True, kind="route"),
            FieldSpec("scu", "Cargo size (SCU)", kind="int"),
            _notes(),
        ),
    ),
    "salvage": Category(
        key="salvage",
        description="Crew or protection for salvage operations",
        label="Salvage",
        emoji="\N{WRENCH}",
        fields=(
            _location(),
            FieldSpec("target", "Target", kind="choice", choices=("Ship wreck", "Panels", "Structure", "Unknown")),
            _notes(),
        ),
    ),
    "escort": Category(
        key="escort",
        description="Fighter cover for your ship or convoy",
        label="Escort",
        emoji="\N{SHIELD}",
        fields=(
            _location(),
            FieldSpec("destination", "Destination", kind="route"),
            _notes(),
        ),
    ),
    "transport": Category(
        key="transport",
        description="A lift from where you are to where you need to be",
        label="Personal Transport",
        emoji="\N{SEAT}",
        fields=(
            _location(),
            FieldSpec("destination", "Destination", kind="route"),
            _notes(),
        ),
    ),
    "contested": Category(
        key="contested",
        description="Group up to run a contested zone",
        label="Contested Zone",
        emoji="\N{HIGH VOLTAGE SIGN}",
        fields=(
            _location(),
            FieldSpec(
                "objective",
                "Objective",
                kind="choice",
                choices=("Vault run", "Full clear", "Keycard run", "Extraction help"),
            ),
            FieldSpec("size", "Group size needed", kind="int"),
            _notes(),
        ),
    ),
}
