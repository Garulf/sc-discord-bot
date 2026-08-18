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


def test_beacon_title_falls_back_to_username():
    assert beacon_title("medic", "Garulf", {}) == "[Medical] Garulf"


def test_beacon_title_medic_shows_tier_and_place():
    fields = {"location": "Stanton:Hurston:Lorville", "tier": "T2"}
    assert beacon_title("medic", "Garulf", fields) == "[Medical] T2 @ Lorville · Garulf"


def test_beacon_title_backup_shows_urgency_and_threat():
    fields = {"location": "Stanton:Daymar", "threat": "Players", "urgency": "Critical"}
    assert beacon_title("backup", "Garulf", fields) == "[Combat Backup] Critical vs Players @ Daymar · Garulf"


def test_beacon_title_cargo_shows_route_and_scu():
    fields = {"route_from": "Stanton:Hurston:Lorville", "route_to": "Stanton:Crusader:Orison", "scu": "64"}
    assert beacon_title("cargo", "Garulf", fields) == "[Cargo] Lorville to Orison (64 SCU) · Garulf"


def test_beacon_title_escort_shows_destination():
    fields = {"location": "Stanton:Hurston:Everus Harbor", "destination": "Stanton:Crusader:Orison"}
    assert beacon_title("escort", "Garulf", fields) == "[Escort] Everus Harbor to Orison · Garulf"


def test_beacon_title_contested_shows_objective():
    fields = {"location": "Pyro:Checkmate", "objective": "Vault run"}
    assert beacon_title("contested", "Garulf", fields) == "[Contested Zone] Vault run @ Checkmate · Garulf"


def test_beacon_title_squad_shows_size():
    fields = {"location": "Stanton:Yela:Grim HEX", "size": "5"}
    assert beacon_title("squad", "Garulf", fields) == "[Squad/FPS] 5 needed @ Grim HEX · Garulf"


def test_beacon_title_is_capped_to_discord_limit():
    fields = {"location": "Stanton:Hurston:" + "x" * 120}
    assert len(beacon_title("mining", "Garulf", fields)) <= 100


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


def test_responders_field_shows_fill_count_when_size_present():
    beacon = _beacon(
        status=STATUS_ACTIVE, members=[7, 8], category="squad", fields={"location": "Stanton", "size": "4"}
    )
    embed = build_beacon_embed(beacon)
    field_names = [f.name for f in embed.fields]
    assert "Responders (2/4)" in field_names


def test_responders_field_plain_without_size():
    embed = build_beacon_embed(_beacon(status=STATUS_ACTIVE, members=[7]))
    field_names = [f.name for f in embed.fields]
    assert "Responders" in field_names


def test_destination_renders_as_breadcrumb():
    beacon = _beacon(
        category="escort",
        fields={"location": "Stanton:Hurston", "destination": "Stanton:Crusader:Orison"},
    )
    embed = build_beacon_embed(beacon)
    values = [f.value for f in embed.fields]
    assert "Stanton › Crusader › Orison" in values
