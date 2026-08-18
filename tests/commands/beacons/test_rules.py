from src.commands.beacons.rules import STATUS_CLAIMED, STATUS_CLOSED, STATUS_OPEN, can_claim, can_close, can_unclaim


def _beacon(status=STATUS_OPEN, requester=1, claimer=None):
    return {"requester_id": requester, "claimer_id": claimer, "status": status}


def test_anyone_but_requester_can_claim_open_beacon():
    assert can_claim(_beacon(), user_id=2)
    assert not can_claim(_beacon(), user_id=1)


def test_cannot_claim_claimed_or_closed_beacon():
    assert not can_claim(_beacon(status=STATUS_CLAIMED, claimer=2), user_id=3)
    assert not can_claim(_beacon(status=STATUS_CLOSED), user_id=2)


def test_only_claimer_can_unclaim():
    beacon = _beacon(status=STATUS_CLAIMED, claimer=2)
    assert can_unclaim(beacon, user_id=2)
    assert not can_unclaim(beacon, user_id=3)
    assert not can_unclaim(_beacon(), user_id=2)


def test_requester_claimer_and_admin_can_close():
    beacon = _beacon(status=STATUS_CLAIMED, requester=1, claimer=2)
    assert can_close(beacon, user_id=1, is_admin=False)
    assert can_close(beacon, user_id=2, is_admin=False)
    assert can_close(beacon, user_id=3, is_admin=True)
    assert not can_close(beacon, user_id=3, is_admin=False)


def test_cannot_close_closed_beacon():
    assert not can_close(_beacon(status=STATUS_CLOSED), user_id=1, is_admin=True)


def test_none_user_id_cannot_close_unclaimed_open_beacon():
    beacon = _beacon(status=STATUS_OPEN, requester=1, claimer=None)
    assert not can_close(beacon, user_id=None, is_admin=False)
