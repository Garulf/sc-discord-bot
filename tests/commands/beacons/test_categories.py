from src.commands.beacons.categories import CATEGORIES, short_label

_EXPECTED_KEYS = {"mining", "medic", "squad", "backup", "cargo", "salvage", "escort", "transport", "contested"}
_EXPECTED_LABELS = {
    "mining": "Mining",
    "medic": "Medical",
    "squad": "Squad/FPS",
    "backup": "Combat Backup",
    "cargo": "Cargo",
    "salvage": "Salvage",
    "escort": "Escort",
    "transport": "Personal Transport",
    "contested": "Contested Zone",
}


def test_all_nine_categories_present():
    assert set(CATEGORIES) == _EXPECTED_KEYS


def test_category_labels():
    assert {key: cat.label for key, cat in CATEGORIES.items()} == _EXPECTED_LABELS


def test_category_keys_match_dict_keys():
    for key, cat in CATEGORIES.items():
        assert cat.key == key


def test_required_fields_per_category():
    for cat in CATEGORIES.values():
        required = [f.key for f in cat.fields if f.required]
        if cat.key == "cargo":
            assert required == ["route_from", "route_to"]
        else:
            assert required == ["location"]


def test_field_keys_are_unique_within_category():
    for cat in CATEGORIES.values():
        keys = [f.key for f in cat.fields]
        assert len(keys) == len(set(keys))


def test_location_and_route_fields_have_location_kinds():
    for cat in CATEGORIES.values():
        for spec in cat.fields:
            if spec.key == "location":
                assert spec.kind == "location"
            if spec.key in ("route_from", "route_to", "destination"):
                assert spec.kind == "route"


def test_choice_fields_declare_their_choices():
    expected = {
        ("mining", "need"),
        ("medic", "tier"),
        ("backup", "threat"),
        ("backup", "urgency"),
        ("salvage", "target"),
        ("contested", "objective"),
        ("medic", "area_status"),
        ("cargo", "area_status"),
        ("escort", "area_status"),
    }
    found = {(cat.key, spec.key) for cat in CATEGORIES.values() for spec in cat.fields if spec.kind == "choice"}
    assert found == expected
    for cat in CATEGORIES.values():
        for spec in cat.fields:
            if spec.kind == "choice":
                assert len(spec.choices) >= 2
                assert all(0 < len(choice) <= 100 for choice in spec.choices)
            else:
                assert spec.choices == ()


def test_int_fields():
    found = {(cat.key, spec.key) for cat in CATEGORIES.values() for spec in cat.fields if spec.kind == "int"}
    assert found == {
        ("squad", "size"),
        ("cargo", "scu"),
        ("contested", "size"),
        ("mining", "size"),
        ("salvage", "size"),
    }


def test_area_status_choices():
    for key in ("medic", "cargo", "escort"):
        spec = next(s for s in CATEGORIES[key].fields if s.key == "area_status")
        assert spec.label == "Area status"
        assert spec.choices == ("Safe", "Unsafe", "Combat expected", "Unknown")


def test_crew_fields_reuse_size_key_for_full_announcements():
    for key in ("mining", "salvage"):
        spec = next(s for s in CATEGORIES[key].fields if s.key == "size")
        assert spec.label == "Crew needed"
        assert spec.kind == "int"


def test_notes_fields_stay_free_text():
    for cat in CATEGORIES.values():
        for spec in cat.fields:
            if spec.key == "notes":
                assert spec.kind == "text"


def test_short_labels_fit_forum_tag_limit():
    for cat in CATEGORIES.values():
        assert 0 < len(short_label(cat)) <= 20


def test_every_category_has_a_description():
    for cat in CATEGORIES.values():
        assert cat.description
        assert len(cat.description) <= 100


def test_contested_stations_cover_named_zones_and_pyam():
    from src.commands.beacons.categories import CONTESTED_STATIONS

    assert {"Orbituary", "Ruin Station", "Checkmate"} <= set(CONTESTED_STATIONS)
    assert all(s.startswith("PYAM-") for s in CONTESTED_STATIONS if s not in ("Orbituary", "Ruin Station", "Checkmate"))
    assert len(CONTESTED_STATIONS) == len(set(CONTESTED_STATIONS))
    assert len(CONTESTED_STATIONS) <= 25
