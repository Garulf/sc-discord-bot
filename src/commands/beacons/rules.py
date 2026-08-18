"""Pure permission and lifecycle rules for beacons."""

from __future__ import annotations

from typing import Any

STATUS_OPEN = "open"
STATUS_CLAIMED = "claimed"
STATUS_CLOSED = "closed"


def can_claim(beacon: dict[str, Any], user_id: int) -> bool:
    return beacon["status"] == STATUS_OPEN and user_id != beacon["requester_id"]


def can_unclaim(beacon: dict[str, Any], user_id: int) -> bool:
    return beacon["status"] == STATUS_CLAIMED and beacon["claimer_id"] == user_id


def can_close(beacon: dict[str, Any], user_id: int, is_admin: bool) -> bool:
    if beacon["status"] == STATUS_CLOSED:
        return False
    return (
        is_admin
        or user_id == beacon["requester_id"]
        or (beacon["claimer_id"] is not None and user_id == beacon["claimer_id"])
    )
