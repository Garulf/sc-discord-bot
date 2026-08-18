"""Pure permission and lifecycle rules for tickets."""

from __future__ import annotations

from typing import Any

STATUS_OPEN = "open"
STATUS_CLAIMED = "claimed"
STATUS_CLOSED = "closed"


def can_claim(ticket: dict[str, Any], user_id: int) -> bool:
    return ticket["status"] == STATUS_OPEN and user_id != ticket["requester_id"]


def can_unclaim(ticket: dict[str, Any], user_id: int) -> bool:
    return ticket["status"] == STATUS_CLAIMED and ticket["claimer_id"] == user_id


def can_close(ticket: dict[str, Any], user_id: int, is_admin: bool) -> bool:
    if ticket["status"] == STATUS_CLOSED:
        return False
    return (
        is_admin
        or user_id == ticket["requester_id"]
        or (ticket["claimer_id"] is not None and user_id == ticket["claimer_id"])
    )
