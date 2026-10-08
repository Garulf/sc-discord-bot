"""Pure manifest rules: cargo, costs, crew weights, sales, payouts and status.

Records are plain dicts so they round-trip through the JSON StateStore. Lists
are used instead of dicts keyed by user id because JSON object keys come back
as strings.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

STATUS_OPEN = "open"
STATUS_PARTIAL = "partial"
STATUS_SOLD = "sold"

MAX_SCU = 1_000_000
MAX_AUEC = 1_000_000_000_000
MAX_WEIGHT = 10
MAX_CREW = 25

Record = dict[str, Any]


class ManifestError(Exception):
    """A rejected manifest change. The message is written for the user."""


@dataclass(frozen=True)
class MemberShare:
    user_id: int
    weight: int | None
    projected: int
    earned: int
    owed: int
    disputed: bool


def _unique(ids: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(ids))


def _build_crew(record: Record, user_ids: Iterable[int]) -> list[Record]:
    weights = {member["user_id"]: member["weight"] for member in record.get("crew", [])}
    ids = _unique([record["created_by"], record["carrier_id"], *user_ids])
    if len(ids) > MAX_CREW:
        raise ManifestError(f"A manifest can have at most {MAX_CREW} crew.")
    return [{"user_id": user_id, "weight": weights.get(user_id, 1)} for user_id in ids]


def new_manifest(
    *,
    manifest_id: int,
    guild_id: int,
    created_by: int,
    carrier_id: int,
    crew_ids: Iterable[int],
    cargo: list[Record],
    costs: list[Record],
    now: float,
    beacon_thread_id: int | None = None,
) -> Record:
    if not cargo:
        raise ManifestError("List at least one commodity.")
    record = {
        "id": manifest_id,
        "guild_id": guild_id,
        "created_by": created_by,
        "created_at": now,
        "beacon_thread_id": beacon_thread_id,
        "thread_id": None,
        "card_message_id": None,
        "carrier_id": carrier_id,
        "crew": [],
        "cargo": [dict(line) for line in cargo],
        "costs": [dict(cost) for cost in costs],
        "sales": [],
    }
    record["crew"] = _build_crew(record, crew_ids)
    return record


def normalize(record: Record) -> Record:
    for key in ("beacon_thread_id", "thread_id", "card_message_id"):
        record.setdefault(key, None)
    for key in ("crew", "cargo", "costs", "sales"):
        record.setdefault(key, [])
    return record


def crew_ids(record: Record) -> list[int]:
    return [member["user_id"] for member in record["crew"]]


def find_cargo(record: Record, commodity: str) -> Record | None:
    needle = commodity.strip().lower()
    return next((line for line in record["cargo"] if line["commodity"].lower() == needle), None)


def _sales_of(record: Record, commodity: str) -> list[Record]:
    needle = commodity.lower()
    return [sale for sale in record["sales"] if sale["commodity"].lower() == needle]


def sold_scu(record: Record, commodity: str) -> int:
    return sum(sale["scu"] for sale in _sales_of(record, commodity))


def unsold_scu(record: Record, line: Record) -> int:
    return line["scu"] - sold_scu(record, line["commodity"])


def total_costs(record: Record) -> int:
    return sum(cost["amount"] for cost in record["costs"])


def recovered_costs(record: Record) -> int:
    return sum(sale["cost_recovered"] for sale in record["sales"])


def outstanding_costs(record: Record) -> int:
    return max(0, total_costs(record) - recovered_costs(record))


def remaining_value(record: Record) -> int:
    return round(sum(unsold_scu(record, line) * (line["est_price"] or 0) for line in record["cargo"]))


def value(record: Record) -> int:
    return sum(sale["total"] for sale in record["sales"]) + remaining_value(record)


def profit(record: Record) -> int:
    return value(record) - total_costs(record)


def status(record: Record) -> str:
    if not record["sales"]:
        return STATUS_OPEN
    if any(unsold_scu(record, line) > 0 for line in record["cargo"]):
        return STATUS_PARTIAL
    return STATUS_SOLD


def is_paid(payout: Record) -> bool:
    return payout["paid_at"] is not None


def unpaid(record: Record) -> list[tuple[Record, Record]]:
    return [(sale, payout) for sale in record["sales"] for payout in sale["payouts"] if not is_paid(payout)]


def owed_amount(record: Record) -> int:
    return sum(payout["amount"] for _, payout in unpaid(record))


def outstanding_payouts(record: Record) -> int:
    return len(unpaid(record))


def _split(amount: int, weights: dict[int, int], remainder_to: int) -> dict[int, int]:
    total_weight = sum(weights.values())
    shares = {user_id: amount * weight // total_weight for user_id, weight in weights.items()}
    shares[remainder_to] += amount - sum(shares.values())
    return shares


def record_sale(record: Record, commodity: str, *, scu: int, total: int, now: float) -> Record:
    line = find_cargo(record, commodity)
    if line is None:
        raise ManifestError(f"Manifest #{record['id']} has no {commodity.strip()}.")
    if scu <= 0:
        raise ManifestError("SCU must be greater than 0.")
    left = unsold_scu(record, line)
    if scu > left:
        raise ManifestError(f"Only {left} SCU of {line['commodity']} is left to sell.")
    if total <= 0:
        raise ManifestError("The sale total must be more than 0 aUEC.")
    recovered = min(total, outstanding_costs(record))
    seller_id = record["carrier_id"]
    weights = {member["user_id"]: member["weight"] for member in record["crew"]}
    amounts = _split(total - recovered, weights, seller_id)
    sale = {
        "id": max((existing["id"] for existing in record["sales"]), default=0) + 1,
        "commodity": line["commodity"],
        "scu": scu,
        "total": total,
        "seller_id": seller_id,
        "sold_at": now,
        "cost_recovered": recovered,
        "payouts": [
            {
                "user_id": user_id,
                "amount": amount,
                "paid_at": now if user_id == seller_id or amount == 0 else None,
                "disputed_at": None,
            }
            for user_id, amount in amounts.items()
        ],
    }
    record["sales"].append(sale)
    return sale


def _payouts_for(record: Record, user_id: int) -> list[Record]:
    return [payout for sale in record["sales"] for payout in sale["payouts"] if payout["user_id"] == user_id]


def _share_of(record: Record, user_id: int, weight: int | None, future: int, total_weight: int) -> MemberShare:
    payouts = _payouts_for(record, user_id)
    earned = sum(payout["amount"] for payout in payouts)
    projected = earned + (future * weight // total_weight if weight else 0)
    return MemberShare(
        user_id=user_id,
        weight=weight,
        projected=projected,
        earned=earned,
        owed=sum(payout["amount"] for payout in payouts if not is_paid(payout)),
        disputed=any(payout["disputed_at"] is not None for payout in payouts),
    )


def member_shares(record: Record) -> list[MemberShare]:
    future = max(0, remaining_value(record) - outstanding_costs(record))
    total_weight = sum(member["weight"] for member in record["crew"])
    shares = [_share_of(record, member["user_id"], member["weight"], future, total_weight) for member in record["crew"]]
    current = set(crew_ids(record))
    former = _unique(
        payout["user_id"] for sale in record["sales"] for payout in sale["payouts"] if payout["user_id"] not in current
    )
    shares += [_share_of(record, user_id, None, future, total_weight) for user_id in former]
    return shares


def replace_cargo(record: Record, cargo: list[Record]) -> None:
    if not cargo:
        raise ManifestError("List at least one commodity.")
    incoming = {line["commodity"].lower(): line for line in cargo}
    for sold in _unique(sale["commodity"] for sale in record["sales"]):
        line = incoming.get(sold.lower())
        if line is None:
            raise ManifestError(f"{sold} has sales, so it can't be removed.")
        already = sold_scu(record, sold)
        if line["scu"] < already:
            raise ManifestError(f"{already} SCU of {sold} is already sold, so the total can't go below that.")
    names = {line["commodity"].lower(): line["commodity"] for line in record["cargo"]}
    record["cargo"] = [{**line, "commodity": names.get(line["commodity"].lower(), line["commodity"])} for line in cargo]


def replace_costs(record: Record, costs: list[Record]) -> None:
    recovered = recovered_costs(record)
    if sum(cost["amount"] for cost in costs) < recovered:
        raise ManifestError(
            f"{recovered:,} aUEC of costs is already recovered from sales, so costs can't total less than that."
        )
    record["costs"] = [dict(cost) for cost in costs]


def set_crew(record: Record, user_ids: Iterable[int]) -> None:
    record["crew"] = _build_crew(record, user_ids)


def set_carrier(record: Record, user_id: int) -> None:
    record["carrier_id"] = user_id
    record["crew"] = _build_crew(record, crew_ids(record))


def set_weight(record: Record, user_id: int, weight: int) -> None:
    if not 1 <= weight <= MAX_WEIGHT:
        raise ManifestError(f"Weight must be between 1 and {MAX_WEIGHT}.")
    member = next((member for member in record["crew"] if member["user_id"] == user_id), None)
    if member is None:
        raise ManifestError(f"<@{user_id}> isn't on manifest #{record['id']}.")
    member["weight"] = weight


def can_edit(record: Record, user_id: int, is_admin: bool) -> bool:
    return is_admin or user_id in (record["created_by"], record["carrier_id"])


def can_sell(record: Record, user_id: int, is_admin: bool) -> bool:
    return is_admin or user_id == record["carrier_id"]


def is_visible(record: Record, user_id: int, is_admin: bool) -> bool:
    return is_admin or user_id == record["created_by"] or user_id in crew_ids(record)


def owes(record: Record, user_id: int) -> list[int]:
    return _unique(payout["user_id"] for sale, payout in unpaid(record) if sale["seller_id"] == user_id)


def mark_paid(record: Record, *, member_id: int | None, seller_id: int | None, now: float) -> int:
    count = 0
    for sale, payout in unpaid(record):
        if seller_id is not None and sale["seller_id"] != seller_id:
            continue
        if member_id is not None and payout["user_id"] != member_id:
            continue
        payout["paid_at"] = now
        payout["disputed_at"] = None
        count += 1
    if count == 0:
        raise ManifestError("Nothing left to mark paid.")
    return count


def dispute(record: Record, *, user_id: int, now: float) -> list[int]:
    sellers = []
    for sale in record["sales"]:
        if sale["seller_id"] == user_id:
            continue
        for payout in sale["payouts"]:
            if payout["user_id"] == user_id and payout["amount"] > 0 and is_paid(payout):
                payout["paid_at"] = None
                payout["disputed_at"] = now
                sellers.append(sale["seller_id"])
    if not sellers:
        raise ManifestError(f"You have no payouts marked paid on manifest #{record['id']}.")
    return _unique(sellers)


def undo_last_sale(record: Record, *, user_id: int, is_admin: bool) -> Record:
    if not record["sales"]:
        raise ManifestError(f"Manifest #{record['id']} has no sales to undo.")
    sale = record["sales"][-1]
    if not is_admin and sale["seller_id"] != user_id:
        raise ManifestError("Only whoever sold it or an officer can undo this sale.")
    others = [payout for payout in sale["payouts"] if payout["user_id"] != sale["seller_id"]]
    if any(is_paid(payout) and payout["amount"] > 0 for payout in others):
        raise ManifestError("Some of this sale's payouts are already marked paid, so it can't be undone.")
    if any(payout["disputed_at"] is not None for payout in others):
        raise ManifestError("This sale has a disputed payout, so it can't be undone. Settle it with the crew first.")
    record["sales"].pop()
    return sale


def can_delete(record: Record) -> bool:
    return owed_amount(record) == 0


def owed_to(records: list[Record], user_id: int) -> list[tuple[Record, Record, Record]]:
    return [
        (record, sale, payout) for record in records for sale, payout in unpaid(record) if payout["user_id"] == user_id
    ]


def owed_by(records: list[Record], user_id: int) -> list[tuple[Record, Record, Record]]:
    return [
        (record, sale, payout) for record in records for sale, payout in unpaid(record) if sale["seller_id"] == user_id
    ]


def carried_by(records: list[Record], user_id: int) -> list[tuple[Record, Record]]:
    return [
        (record, line)
        for record in records
        if record["carrier_id"] == user_id
        for line in record["cargo"]
        if unsold_scu(record, line) > 0
    ]
