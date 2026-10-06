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

MAX_SCU = 1_000_000

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


def _lines_for(record: Record, commodity: str) -> list[Record]:
    needle = commodity.strip().lower()
    return [line for line in record["cargo"] if line["commodity"].lower() == needle]


def find_line(record: Record, commodity: str, holder_id: int | None = None) -> Record | None:
    return next(
        (line for line in _lines_for(record, commodity) if holder_id is None or line["holder_id"] == holder_id),
        None,
    )


def _join_mentions(user_ids: list[int]) -> str:
    mentions = [f"<@{user_id}>" for user_id in user_ids]
    if len(mentions) == 1:
        return mentions[0]
    return f"{', '.join(mentions[:-1])} and {mentions[-1]}"


def resolve_line(record: Record, commodity: str, user_id: int) -> Record:
    """The line a commodity command acts on: the caller's own, else the only one."""
    lines = _lines_for(record, commodity)
    if not lines:
        raise LootError(f"Raid #{record['id']} has no {commodity.strip()} cargo.")
    own = next((line for line in lines if line["holder_id"] == user_id), None)
    if own is not None:
        return own
    if len(lines) == 1:
        return lines[0]
    holders = _join_mentions(_unique(line["holder_id"] for line in lines))
    raise LootError(f"Raid #{record['id']} has {lines[0]['commodity']} held by {holders}. Ask the holder to run this.")


def unsold_scu(line: Record) -> int:
    return line["scu"] - line["sold_scu"]


def add_cargo(record: Record, commodity: str, scu: int, holder_id: int) -> Record:
    commodity = commodity.strip()
    if not commodity:
        raise LootError("Commodity can't be empty.")
    if scu <= 0:
        raise LootError("SCU must be greater than 0.")
    line = find_line(record, commodity, holder_id)
    if line is None:
        existing = find_line(record, commodity)
        name = existing["commodity"] if existing is not None else commodity
        line = {"commodity": name, "scu": 0, "sold_scu": 0, "holder_id": holder_id}
        record["cargo"].append(line)
    line["scu"] += scu
    return line


def split(total: int, count: int) -> tuple[int, int]:
    return total // count, total % count


def is_paid(payout: Record) -> bool:
    return payout["paid_at"] is not None


def record_sale(record: Record, line: Record, *, scu: int, total: int, now: float) -> Record:
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


def parse_mentions(text: str | None) -> list[int]:
    if not text:
        return []
    return _unique(int(match) for match in _MENTION.findall(text))


def can_handle_line(line: Record, user_id: int, is_admin: bool) -> bool:
    return is_admin or line["holder_id"] == user_id


def can_manage_roster(record: Record, user_id: int, is_admin: bool) -> bool:
    if is_admin or user_id in record["organizer_ids"]:
        return True
    return any(line["holder_id"] == user_id for line in record["cargo"])


def can_delete(record: Record) -> bool:
    return owed_amount(record) == 0


def add_participant(record: Record, user_id: int) -> None:
    if record["sales"] and status(record) == STATUS_SETTLED:
        raise LootError(f"Raid #{record['id']} is settled.")
    if user_id in record["participants"]:
        raise LootError(f"<@{user_id}> is already on raid #{record['id']}.")
    record["participants"].append(user_id)


def remove_participant(record: Record, user_id: int) -> None:
    if user_id not in record["participants"]:
        raise LootError(f"<@{user_id}> isn't on raid #{record['id']}.")
    record["participants"].remove(user_id)


def set_holder(record: Record, line: Record, holder_id: int) -> Record:
    existing = next(
        (
            other
            for other in _lines_for(record, line["commodity"])
            if other is not line and other["holder_id"] == holder_id
        ),
        None,
    )
    if existing is None:
        line["holder_id"] = holder_id
        return line
    existing["scu"] += line["scu"]
    existing["sold_scu"] += line["sold_scu"]
    record["cargo"].remove(line)
    return existing


def fix_cargo(record: Record, line: Record, scu: int) -> Record | None:
    if scu < 0:
        raise LootError("SCU can't be negative.")
    if scu < line["sold_scu"]:
        raise LootError(
            f"{line['sold_scu']} SCU of {line['commodity']} is already sold, so the total can't go below that."
        )
    if scu == 0:
        record["cargo"].remove(line)
        return None
    line["scu"] = scu
    return line


def mark_paid(record: Record, *, member_id: int | None, seller_id: int | None, now: float) -> int:
    count = 0
    for sale, payout in _unpaid(record):
        if seller_id is not None and sale["seller_id"] != seller_id:
            continue
        if member_id is not None and payout["user_id"] != member_id:
            continue
        payout["paid_at"] = now
        payout["disputed_at"] = None
        count += 1
    if count == 0:
        raise LootError("Nothing left to mark paid.")
    return count


def dispute(record: Record, *, user_id: int, now: float) -> list[int]:
    payers = []
    for sale in record["sales"]:
        if sale["seller_id"] == user_id:
            continue
        for payout in sale["payouts"]:
            if payout["user_id"] == user_id and is_paid(payout):
                payout["paid_at"] = None
                payout["disputed_at"] = now
                payers.append(sale["seller_id"])
    if not payers:
        raise LootError(f"You have no payouts marked paid on raid #{record['id']}.")
    return _unique(payers)


def _sale_line(record: Record, sale: Record) -> Record:
    return find_line(record, sale["commodity"], sale["seller_id"]) or resolve_line(
        record, sale["commodity"], sale["seller_id"]
    )


def undo_last_sale(record: Record, *, user_id: int, is_admin: bool) -> Record:
    if not record["sales"]:
        raise LootError(f"Raid #{record['id']} has no sales to undo.")
    sale = record["sales"][-1]
    if not is_admin and sale["seller_id"] != user_id:
        raise LootError("Only the seller or an admin can undo this sale.")
    if any(is_paid(p) for p in sale["payouts"] if p["user_id"] != sale["seller_id"]):
        raise LootError("Some of this sale's payouts are already marked paid, so it can't be undone.")
    if any(p["disputed_at"] is not None for p in sale["payouts"]):
        raise LootError("This sale has a disputed payout. Sort it out and mark it paid before undoing.")
    _sale_line(record, sale)["sold_scu"] -= sale["scu"]
    record["sales"].pop()
    return sale


def owed_to(records: list[Record], user_id: int) -> list[tuple[Record, Record, Record]]:
    return [
        (record, sale, payout) for record in records for sale, payout in _unpaid(record) if payout["user_id"] == user_id
    ]


def owed_by(records: list[Record], user_id: int) -> list[tuple[Record, Record, Record]]:
    return [
        (record, sale, payout) for record in records for sale, payout in _unpaid(record) if sale["seller_id"] == user_id
    ]


def held_by(records: list[Record], user_id: int) -> list[tuple[Record, Record]]:
    return [
        (record, line)
        for record in records
        for line in record["cargo"]
        if line["holder_id"] == user_id and unsold_scu(line) > 0
    ]
