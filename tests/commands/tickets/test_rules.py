from src.commands.tickets.rules import STATUS_CLAIMED, STATUS_CLOSED, STATUS_OPEN, can_claim, can_close, can_unclaim


def _ticket(status=STATUS_OPEN, requester=1, claimer=None):
    return {"requester_id": requester, "claimer_id": claimer, "status": status}


def test_anyone_but_requester_can_claim_open_ticket():
    assert can_claim(_ticket(), user_id=2)
    assert not can_claim(_ticket(), user_id=1)


def test_cannot_claim_claimed_or_closed_ticket():
    assert not can_claim(_ticket(status=STATUS_CLAIMED, claimer=2), user_id=3)
    assert not can_claim(_ticket(status=STATUS_CLOSED), user_id=2)


def test_only_claimer_can_unclaim():
    ticket = _ticket(status=STATUS_CLAIMED, claimer=2)
    assert can_unclaim(ticket, user_id=2)
    assert not can_unclaim(ticket, user_id=3)
    assert not can_unclaim(_ticket(), user_id=2)


def test_requester_claimer_and_admin_can_close():
    ticket = _ticket(status=STATUS_CLAIMED, requester=1, claimer=2)
    assert can_close(ticket, user_id=1, is_admin=False)
    assert can_close(ticket, user_id=2, is_admin=False)
    assert can_close(ticket, user_id=3, is_admin=True)
    assert not can_close(ticket, user_id=3, is_admin=False)


def test_cannot_close_closed_ticket():
    assert not can_close(_ticket(status=STATUS_CLOSED), user_id=1, is_admin=True)
