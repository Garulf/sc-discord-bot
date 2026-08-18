"""Ticket category definitions: labels, emoji, and per-category form fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    required: bool = False


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    emoji: str
    fields: tuple[FieldSpec, ...]


CATEGORIES: dict[str, Category] = {
    "mining": Category(
        key="mining",
        label="Mining",
        emoji="\N{PICK}",
        fields=(
            FieldSpec("location", "Location", required=True),
            FieldSpec("need", "What do you need?"),
            FieldSpec("notes", "Notes"),
        ),
    ),
    "medic": Category(
        key="medic",
        label="Medic",
        emoji="\N{ADHESIVE BANDAGE}",
        fields=(
            FieldSpec("location", "Location", required=True),
            FieldSpec("tier", "Injury tier"),
            FieldSpec("notes", "Notes"),
        ),
    ),
    "squad": Category(
        key="squad",
        label="Squad/FPS",
        emoji="\N{CROSSED SWORDS}",
        fields=(
            FieldSpec("location", "Location", required=True),
            FieldSpec("size", "Squad size needed"),
            FieldSpec("notes", "Notes"),
        ),
    ),
    "backup": Category(
        key="backup",
        label="Backup (under attack)",
        emoji="\N{POLICE CARS REVOLVING LIGHT}",
        fields=(
            FieldSpec("location", "Location", required=True),
            FieldSpec("threat", "Threat"),
            FieldSpec("urgency", "Urgency"),
        ),
    ),
    "cargo": Category(
        key="cargo",
        label="Cargo",
        emoji="\N{PACKAGE}",
        fields=(
            FieldSpec("route_from", "Route from", required=True),
            FieldSpec("route_to", "Route to", required=True),
            FieldSpec("scu", "Cargo size (SCU)"),
            FieldSpec("notes", "Notes"),
        ),
    ),
    "salvage": Category(
        key="salvage",
        label="Salvage",
        emoji="\N{WRENCH}",
        fields=(
            FieldSpec("location", "Location", required=True),
            FieldSpec("target", "Target"),
            FieldSpec("notes", "Notes"),
        ),
    ),
}
