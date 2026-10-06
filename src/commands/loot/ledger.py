"""Pure loot ledger rules: cargo, sales, equal-share payouts, roster, and status.

Records are plain dicts so they round-trip through the JSON StateStore. Payouts
are a list rather than a dict keyed by user id because JSON object keys come
back as strings.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

STATUS_HOLDING = "holding"
STATUS_PAYING = "paying out"
STATUS_SETTLED = "settled"

_MENTION = re.compile(r"<@!?(\d+)>")

Record = dict[str, Any]


class LootError(Exception):
    """A rejected loot change. The message is written for the user."""


def _unique(ids: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(ids))


def new_record(
    *,
    loot_id: int,
    guild_id: int,
    title: str,
    created_by: int,
    participants: list[int],
    organizer_ids: list[int],
    now: float,
    beacon_thread_id: int | None = None,
    category: str | None = None,
) -> Record:
    title = title.strip()
    if not title:
        raise LootError("Give the raid a title.")
    return {
        "id": loot_id,
        "guild_id": guild_id,
        "beacon_thread_id": beacon_thread_id,
        "category": category,
        "title": title,
        "created_by": created_by,
        "created_at": now,
        "organizer_ids": _unique(organizer_ids),
        "participants": _unique(participants),
        "cargo": [],
        "sales": [],
        "card": None,
    }


def normalize_loot(record: Record) -> Record:
    record.setdefault("beacon_thread_id", None)
    record.setdefault("category", None)
    record.setdefault("organizer_ids", [record["created_by"]])
    record.setdefault("participants", [])
    record.setdefault("cargo", [])
    record.setdefault("sales", [])
    record.setdefault("card", None)
    for sale in record["sales"]:
        for payout in sale["payouts"]:
            payout.setdefault("paid_at", None)
            payout.setdefault("disputed_at", None)
    return record


def find_line(record: Record, commodity: str) -> Record | None:
    needle = commodity.strip().lower()
    return next((line for line in record["cargo"] if line["commodity"].lower() == needle), None)


def require_line(record: Record, commodity: str) -> Record:
    line = find_line(record, commodity)
    if line is None:
        raise LootError(f"Raid #{record['id']} has no {commodity.strip()} cargo.")
    return line


def unsold_scu(line: Record) -> int:
    return line["scu"] - line["sold_scu"]


def add_cargo(record: Record, commodity: str, scu: int, holder_id: int) -> Record:
    commodity = commodity.strip()
    if not commodity:
        raise LootError("Commodity can't be empty.")
    if scu <= 0:
        raise LootError("SCU must be greater than 0.")
    line = find_line(record, commodity)
    if line is None:
        line = {"commodity": commodity, "scu": 0, "sold_scu": 0, "holder_id": holder_id}
        record["cargo"].append(line)
    line["scu"] += scu
    return line


def split(total: int, count: int) -> tuple[int, int]:
    return total // count, total % count


def is_paid(payout: Record) -> bool:
    return payout["paid_at"] is not None


def record_sale(record: Record, *, commodity: str, scu: int, total: int, now: float) -> Record:
    line = require_line(record, commodity)
    if scu <= 0:
        raise LootError("SCU must be greater than 0.")
    left = unsold_scu(line)
    if scu > left:
        raise LootError(f"Only {left} SCU of {line['commodity']} is left to sell.")
    if total <= 0:
        raise LootError("The sale total must be more than 0 aUEC.")
    if not record["participants"]:
        raise LootError("This raid has no participants to pay. Add some with `/loot participants add`.")
    seller_id = line["holder_id"]
    share, _ = split(total, len(record["participants"]))
    sale = {
        "id": max((existing["id"] for existing in record["sales"]), default=0) + 1,
        "commodity": line["commodity"],
        "scu": scu,
        "total": total,
        "share": share,
        "seller_id": seller_id,
        "sold_at": now,
        "payouts": [
            {"user_id": user_id, "amount": share, "paid_at": now if user_id == seller_id else None, "disputed_at": None}
            for user_id in record["participants"]
        ],
    }
    line["sold_scu"] += scu
    record["sales"].append(sale)
    return sale


def _unpaid(record: Record) -> list[tuple[Record, Record]]:
    return [(sale, payout) for sale in record["sales"] for payout in sale["payouts"] if not is_paid(payout)]


def owed_amount(record: Record) -> int:
    return sum(payout["amount"] for _, payout in _unpaid(record))


def status(record: Record) -> str:
    if not record["cargo"] or any(unsold_scu(line) > 0 for line in record["cargo"]):
        return STATUS_HOLDING
    if _unpaid(record):
        return STATUS_PAYING
    return STATUS_SETTLED
