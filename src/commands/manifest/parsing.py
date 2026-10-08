"""Cargo and cost lists as editable text, one entry per line.

Cargo lines are `<commodity> <scu> [est price per SCU]`; cost lines are
`<label> <amount>`. Numbers are read from the end of the line so names can
contain spaces.
"""

from __future__ import annotations

import re

from .ledger import MAX_AUEC, MAX_SCU, ManifestError, Record

MAX_LINES = 20

_NUMBER = re.compile(r"^-?\d[\d,]*(\.\d+)?$")


class _LineError(Exception):
    pass


def _split_trailing_numbers(line: str) -> tuple[str, list[str]]:
    tokens = line.split()
    numbers: list[str] = []
    while tokens and _NUMBER.match(tokens[-1]):
        numbers.insert(0, tokens.pop())
    return " ".join(tokens), numbers


def _number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _whole(raw: str, what: str, maximum: int) -> int:
    number = _number(raw)
    if not number.is_integer():
        raise _LineError(f"{what} must be a whole number.")
    if not 0 < number <= maximum:
        raise _LineError(f"{what} must be between 1 and {maximum:,}.")
    return int(number)


def _price(raw: str) -> float:
    price = _number(raw)
    if not 0 <= price <= MAX_AUEC:
        raise _LineError("Price per SCU can't be negative.")
    return price


def _cargo_line(line: str) -> Record:
    name, numbers = _split_trailing_numbers(line)
    if not name:
        raise _LineError("Start the line with the commodity name.")
    if not numbers:
        raise _LineError(f"Add the SCU after {name}, e.g. `{name} 96`.")
    if len(numbers) > 2:
        raise _LineError("Use `<commodity> <scu> [price per SCU]`.")
    scu = _whole(numbers[0], "SCU", MAX_SCU)
    price = _price(numbers[1]) if len(numbers) == 2 else None
    return {"commodity": name, "scu": scu, "est_price": price}


def _cost_line(line: str) -> Record:
    label, numbers = _split_trailing_numbers(line)
    if not label:
        raise _LineError("Start the line with what the cost was for.")
    if len(numbers) != 1:
        raise _LineError(f"Use `<label> <amount>`, e.g. `{label} 20000`.")
    return {"label": label, "amount": _whole(numbers[0], "Amount", MAX_AUEC)}


def _parse_lines(text: str, parse_line) -> list[Record]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > MAX_LINES:
        raise ManifestError(f"Keep it to {MAX_LINES} lines or fewer.")
    entries, problems = [], []
    for number, line in enumerate(lines, start=1):
        try:
            entries.append(parse_line(line))
        except _LineError as error:
            problems.append(f"Line {number}: {error}")
    if problems:
        raise ManifestError("\n".join(problems))
    return entries


def merge_cargo(lines: list[Record]) -> list[Record]:
    merged: dict[str, Record] = {}
    for line in lines:
        key = line["commodity"].lower()
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(line)
            continue
        existing["scu"] += line["scu"]
        if line["est_price"] is not None:
            existing["est_price"] = line["est_price"]
    return list(merged.values())


def parse_cargo(text: str) -> list[Record]:
    cargo = merge_cargo(_parse_lines(text, _cargo_line))
    if not cargo:
        raise ManifestError("List at least one commodity, e.g. `Gold 96`.")
    too_big = [line["commodity"] for line in cargo if line["scu"] > MAX_SCU]
    if too_big:
        raise ManifestError(f"{', '.join(too_big)} adds up to more than {MAX_SCU:,} SCU.")
    return cargo


def parse_costs(text: str) -> list[Record]:
    return _parse_lines(text, _cost_line)


def _format_number(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


def format_cargo(cargo: list[Record]) -> str:
    return "\n".join(
        f"{line['commodity']} {line['scu']}"
        + (f" {_format_number(line['est_price'])}" if line["est_price"] is not None else "")
        for line in cargo
    )


def format_costs(costs: list[Record]) -> str:
    return "\n".join(f"{cost['label']} {cost['amount']}" for cost in costs)
