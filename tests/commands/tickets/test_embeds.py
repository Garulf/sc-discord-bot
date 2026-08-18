from src.commands.tickets.embeds import build_panel_embed, build_ticket_embed, ticket_title
from src.commands.tickets.rules import STATUS_CLAIMED, STATUS_CLOSED, STATUS_OPEN


def _ticket(**overrides):
    ticket = {
        "guild_id": 1,
        "category": "medic",
        "requester_id": 42,
        "claimer_id": None,
        "status": STATUS_OPEN,
        "opened_at": 123.0,
        "closed_at": None,
        "closed_by_id": None,
        "fields": {"location": "Stanton:Hurston:Lorville", "tier": "T2"},
    }
    ticket.update(overrides)
    return ticket


def test_ticket_title():
    assert ticket_title("medic", "Garulf") == "[Medic] Garulf"


def test_open_embed_shows_category_requester_and_fields():
    embed = build_ticket_embed(_ticket())
    assert "Medic" in embed.title
    field_names = [f.name for f in embed.fields]
    field_values = [f.value for f in embed.fields]
    assert "Location" in field_names
    assert "Stanton › Hurston › Lorville" in field_values
    assert any("<@42>" in v for v in field_values)
    assert any("Open" in v for v in field_values)


def test_claimed_embed_mentions_claimer():
    embed = build_ticket_embed(_ticket(status=STATUS_CLAIMED, claimer_id=7))
    assert any("<@7>" in f.value for f in embed.fields)


def test_closed_embed_mentions_closer():
    embed = build_ticket_embed(_ticket(status=STATUS_CLOSED, closed_by_id=7, closed_at=999.0))
    values = " ".join(f.value for f in embed.fields)
    assert "Closed" in values
    assert "<@7>" in values


def test_unsubmitted_fields_are_omitted():
    embed = build_ticket_embed(_ticket(fields={"location": "Stanton"}))
    assert "Injury tier" not in [f.name for f in embed.fields]


def test_panel_embed_lists_all_categories():
    embed = build_panel_embed()
    description = embed.description or ""
    for label in ("Mining", "Medic", "Squad/FPS", "Backup", "Cargo", "Salvage"):
        assert label in description
