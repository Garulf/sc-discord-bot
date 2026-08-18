from src.commands.beacons.rules import (
    STATUS_ACTIVE,
    STATUS_CLOSED,
    STATUS_OPEN,
    can_close,
    can_join,
    can_leave,
    normalize_beacon,
)


def _beacon(status=STATUS_OPEN, requester=1, members=()):
    return {"requester_id": requester, "members": list(members), "status": status}


def test_anyone_but_requester_can_join_open_beacon():
    assert can_join(_beacon(), user_id=2)
    assert not can_join(_beacon(), user_id=1)


def test_more_responders_can_join_an_active_beacon():
    assert can_join(_beacon(status=STATUS_ACTIVE, members=[2]), user_id=3)


def test_existing_member_cannot_join_again():
    assert not can_join(_beacon(status=STATUS_ACTIVE, members=[2]), user_id=2)


def test_cannot_join_closed_beacon():
    assert not can_join(_beacon(status=STATUS_CLOSED), user_id=2)


def test_only_members_can_leave():
    beacon = _beacon(status=STATUS_ACTIVE, members=[2])
    assert can_leave(beacon, user_id=2)
    assert not can_leave(beacon, user_id=3)
    assert not can_leave(_beacon(status=STATUS_CLOSED, members=[2]), user_id=2)


def test_requester_members_and_admin_can_close():
    beacon = _beacon(status=STATUS_ACTIVE, requester=1, members=[2])
    assert can_close(beacon, user_id=1, is_admin=False)
    assert can_close(beacon, user_id=2, is_admin=False)
    assert can_close(beacon, user_id=3, is_admin=True)
    assert not can_close(beacon, user_id=3, is_admin=False)


def test_cannot_close_closed_beacon():
    assert not can_close(_beacon(status=STATUS_CLOSED), user_id=1, is_admin=True)


def test_none_user_id_cannot_close_unclaimed_open_beacon():
    assert not can_close(_beacon(), user_id=None, is_admin=False)


def test_normalize_converts_claimed_records():
    legacy = {"requester_id": 1, "claimer_id": 7, "status": "claimed"}
    beacon = normalize_beacon(legacy)
    assert beacon["status"] == STATUS_ACTIVE
    assert beacon["members"] == [7]


def test_normalize_converts_open_legacy_records():
    legacy = {"requester_id": 1, "claimer_id": None, "status": STATUS_OPEN}
    beacon = normalize_beacon(legacy)
    assert beacon["members"] == []
    assert beacon["status"] == STATUS_OPEN


def test_normalize_passes_through_current_records():
    current = _beacon(status=STATUS_ACTIVE, members=[2, 3])
    assert normalize_beacon(dict(current)) == current
