from src.commands.beacons.categories import CATEGORIES


def test_all_six_categories_present():
    assert set(CATEGORIES) == {"mining", "medic", "squad", "backup", "cargo", "salvage"}


def test_category_keys_match_dict_keys():
    for key, cat in CATEGORIES.items():
        assert cat.key == key


def test_every_category_has_exactly_one_required_field_set():
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
