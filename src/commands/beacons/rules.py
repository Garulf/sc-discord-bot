"""Pure permission and lifecycle rules for beacons."""

from __future__ import annotations

from typing import Any

STATUS_OPEN = "open"
STATUS_ACTIVE = "active"
STATUS_CLOSED = "closed"

_LEGACY_STATUS = {"claimed": STATUS_ACTIVE}


def normalize_beacon(beacon: dict[str, Any]) -> dict[str, Any]:
    """Upgrade pre-join records: claimer_id becomes the members list."""
    if "members" not in beacon:
        claimer = beacon.pop("claimer_id", None)
        beacon["members"] = [claimer] if claimer is not None else []
    beacon["status"] = _LEGACY_STATUS.get(beacon["status"], beacon["status"])
    return beacon


def can_join(beacon: dict[str, Any], user_id: int) -> bool:
    if beacon["status"] == STATUS_CLOSED:
        return False
    return user_id != beacon["requester_id"] and user_id not in beacon["members"]


def can_leave(beacon: dict[str, Any], user_id: int) -> bool:
    return beacon["status"] != STATUS_CLOSED and user_id in beacon["members"]


def can_close(beacon: dict[str, Any], user_id: int, is_admin: bool) -> bool:
    if beacon["status"] == STATUS_CLOSED:
        return False
    if is_admin:
        return True
    return user_id is not None and (user_id == beacon["requester_id"] or user_id in beacon["members"])
