from src.commands.beacons.embeds import beacon_title, build_beacon_embed, build_panel_embed
from src.commands.beacons.rules import STATUS_CLAIMED, STATUS_CLOSED, STATUS_OPEN


def _beacon(**overrides):
    beacon = {
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
    beacon.update(overrides)
    return beacon


def test_beacon_title():
    assert beacon_title("medic", "Garulf") == "[Medical] Garulf"


def test_open_embed_shows_category_requester_and_fields():
    embed = build_beacon_embed(_beacon())
    assert "Medical" in embed.title
    field_names = [f.name for f in embed.fields]
    field_values = [f.value for f in embed.fields]
    assert "Location" in field_names
    assert "Stanton › Hurston › Lorville" in field_values
    assert any("<@42>" in v for v in field_values)
    assert any("Open" in v for v in field_values)


def test_claimed_embed_mentions_claimer():
    embed = build_beacon_embed(_beacon(status=STATUS_CLAIMED, claimer_id=7))
    assert any("<@7>" in f.value for f in embed.fields)


def test_closed_embed_mentions_closer():
    embed = build_beacon_embed(_beacon(status=STATUS_CLOSED, closed_by_id=7, closed_at=999.0))
    values = " ".join(f.value for f in embed.fields)
    assert "Closed" in values
    assert "<@7>" in values


def test_unsubmitted_fields_are_omitted():
    embed = build_beacon_embed(_beacon(fields={"location": "Stanton"}))
    assert "Injury tier" not in [f.name for f in embed.fields]


def test_panel_embed_lists_all_categories():
    embed = build_panel_embed()
    description = embed.description or ""
    for label in (
        "Mining",
        "Medical",
        "Squad/FPS",
        "Combat Backup",
        "Cargo",
        "Salvage",
        "Escort",
        "Personal Transport",
    ):
        assert label in description


def test_destination_renders_as_breadcrumb():
    beacon = _beacon(
        category="escort",
        fields={"location": "Stanton:Hurston", "destination": "Stanton:Crusader:Orison"},
    )
    embed = build_beacon_embed(beacon)
    values = [f.value for f in embed.fields]
    assert "Stanton › Crusader › Orison" in values


def test_panel_embed_describes_each_category():
    from src.commands.beacons.categories import CATEGORIES

    embed = build_panel_embed()
    description = embed.description or ""
    for cat in CATEGORIES.values():
        assert cat.description in description
