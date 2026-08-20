from src.commands.beacons.duration import MAX_SECONDS, MIN_SECONDS, parse_duration


def test_parses_minutes():
    assert parse_duration("45m") == 45 * 60


def test_parses_hours():
    assert parse_duration("2h") == 2 * 3600


def test_parses_combined_hours_and_minutes():
    assert parse_duration("1h30m") == 90 * 60


def test_parses_days():
    assert parse_duration("1d") == 86400


def test_is_case_insensitive_and_ignores_spaces():
    assert parse_duration(" 1H 30M ") == 90 * 60


def test_rejects_empty_string():
    assert parse_duration("") is None


def test_rejects_unparseable_text():
    assert parse_duration("soon") is None


def test_rejects_below_minimum():
    assert parse_duration("4m") is None


def test_accepts_minimum_boundary():
    assert parse_duration("5m") == MIN_SECONDS


def test_rejects_above_maximum():
    assert parse_duration("25h") is None


def test_accepts_maximum_boundary():
    assert parse_duration("24h") == MAX_SECONDS
