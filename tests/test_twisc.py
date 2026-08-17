from src.commands.twisc import ScheduleDay, parse_schedule

SAMPLE_CONTENT = (
    "Happy Monday, everyone!\n"
    "Last week, we published the PU Monthly Report.\n\n"
    "Fly low, and fly fast!\n\n"
    "The Weekly Community Content Schedule\n\n\n"
    "MONDAY, AUGUST 10, 2026\nThis Week in Star Citizen\n\n"
    "TUESDAY, AUGUST 11, 2026\nAugust 2026 Monthly Bundle\n\n"
    "Maintenance: Issue Council, starting at 13:00 UTC\n\n"
    "WEDNESDAY, AUGUST 12, 2026\nRoadmap Update\n\n"
    "Roadmap Roundup\n\n"
    "FRIDAY, AUGUST 14, 2026\nRSI Weekly Newsletter\n\n"
    "SATURDAY, AUGUST 15, 2026\nBar Citizen World Tour 2026 - Denver, Colorado (USA)\n\n"
    "Freyja Vanadis\nSenior Community Manager\n\n"
    "SourcePilotVision quest truth trailing lore text"
)


def test_parse_schedule_extracts_days_and_items():
    days = parse_schedule(SAMPLE_CONTENT)
    assert [d.heading for d in days] == [
        "MONDAY, AUGUST 10, 2026",
        "TUESDAY, AUGUST 11, 2026",
        "WEDNESDAY, AUGUST 12, 2026",
        "FRIDAY, AUGUST 14, 2026",
        "SATURDAY, AUGUST 15, 2026",
    ]
    assert days[0].items == ("This Week in Star Citizen",)
    assert days[1].items == (
        "August 2026 Monthly Bundle",
        "Maintenance: Issue Council, starting at 13:00 UTC",
    )


def test_parse_schedule_stops_at_signoff():
    days = parse_schedule(SAMPLE_CONTENT)
    all_items = [item for day in days for item in day.items]
    assert not any("Freyja" in item or "Source" in item for item in all_items)


def test_parse_schedule_missing_marker_returns_empty():
    assert parse_schedule("Happy Monday, everyone! No schedule here.") == []


def test_parse_schedule_none_returns_empty():
    assert parse_schedule(None) == []


def test_parse_schedule_junk_after_marker_returns_empty():
    content = "The Weekly Community Content Schedule\n\nSome unexpected paragraph instead of a day"
    assert parse_schedule(content) == []


def test_schedule_day_is_frozen():
    day = ScheduleDay(heading="MONDAY, AUGUST 10, 2026", items=("x",))
    assert day.heading == "MONDAY, AUGUST 10, 2026"
