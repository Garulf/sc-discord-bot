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
        label="Personal Transport",
        emoji="\N{SEAT}",
        fields=(
            _location(),
            FieldSpec("destination", "Destination", kind="route"),
            _notes(),
        ),
    ),
}
