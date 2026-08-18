from src.commands.beacons.embeds import beacon_title, build_beacon_embed, build_panel_content
from src.commands.beacons.rules import STATUS_ACTIVE, STATUS_CLOSED, STATUS_OPEN


def _beacon(**overrides):
    beacon = {
        "guild_id": 1,
        "category": "medic",
        "requester_id": 42,
        "members": [],
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


def test_active_embed_lists_responders():
    embed = build_beacon_embed(_beacon(status=STATUS_ACTIVE, members=[7, 8]))
    values = " ".join(f.value for f in embed.fields)
    assert "Active" in values
    assert "<@7>" in values
    assert "<@8>" in values


def test_closed_embed_mentions_closer():
    embed = build_beacon_embed(_beacon(status=STATUS_CLOSED, closed_by_id=7, closed_at=999.0))
    values = " ".join(f.value for f in embed.fields)
    assert "Closed" in values
    assert "<@7>" in values


def test_unsubmitted_fields_are_omitted():
    embed = build_beacon_embed(_beacon(fields={"location": "Stanton"}))
    assert "Injury tier" not in [f.name for f in embed.fields]


def test_panel_content_links_and_describes_each_category():
    from src.commands.beacons.categories import CATEGORIES

    content = build_panel_content(lambda key: f"</beacon {key}:1>")
    for cat in CATEGORIES.values():
        assert f"</beacon {cat.key}:1>" in content
        assert cat.description in content


def test_destination_renders_as_breadcrumb():
    beacon = _beacon(
        category="escort",
        fields={"location": "Stanton:Hurston", "destination": "Stanton:Crusader:Orison"},
    )
    embed = build_beacon_embed(beacon)
    values = [f.value for f in embed.fields]
    assert "Stanton › Crusader › Orison" in values
