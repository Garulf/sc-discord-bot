from unittest.mock import AsyncMock, MagicMock

from src.commands.twisc import ScheduleDay, parse_schedule
from src.starcitizenwiki_api.comm_links import CommLink

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


def test_parse_schedule_day_with_three_items_then_another_day():
    content = (
        "The Weekly Community Content Schedule\n\n\n"
        "MONDAY, AUGUST 10, 2026\nItem One\n\n"
        "Item Two\n\n"
        "Item Three\n\n"
        "TUESDAY, AUGUST 11, 2026\nOnly Item\n\n"
        "Freyja Vanadis\nSenior Community Manager\n\n"
        "SourcePilotVision quest truth trailing lore text"
    )
    days = parse_schedule(content)
    assert [d.heading for d in days] == [
        "MONDAY, AUGUST 10, 2026",
        "TUESDAY, AUGUST 11, 2026",
    ]
    assert days[0].items == ("Item One", "Item Two", "Item Three")
    assert days[1].items == ("Only Item",)
    all_items = [item for day in days for item in day.items]
    assert not any("Freyja" in item or "Source" in item for item in all_items)


SAMPLE_CONTENT_NO_YEAR = (
    "The Weekly Community Content Schedule\n\n\n"
    "MONDAY, AUGUST 17\nThis Week in Star Citizen\n\n"
    "TUESDAY, AUGUST 18\nAugust 2026 Monthly Bundle\n\n"
    "Freyja Vanadis\nSenior Community Manager\n\n"
    "SourcePilotVision quest truth trailing lore text"
)


def test_parse_schedule_handles_headings_without_year():
    days = parse_schedule(SAMPLE_CONTENT_NO_YEAR)
    assert [d.heading for d in days] == [
        "MONDAY, AUGUST 17",
        "TUESDAY, AUGUST 18",
    ]
    assert days[0].items == ("This Week in Star Citizen",)
    assert days[1].items == ("August 2026 Monthly Bundle",)


def test_build_schedule_embed_field_name_without_year():
    from src.commands.twisc import build_schedule_embed

    days = parse_schedule(SAMPLE_CONTENT_NO_YEAR)
    embed = build_schedule_embed(_comm_link(), days)
    assert embed.fields[0].name == "Monday, August 17"


def test_schedule_day_is_frozen():
    day = ScheduleDay(heading="MONDAY, AUGUST 10, 2026", items=("x",))
    assert day.heading == "MONDAY, AUGUST 10, 2026"


def _comm_link(rsi_url="https://robertsspaceindustries.com/comm-link/transmission/21287"):
    return CommLink(
        id=21287,
        title="This Week in Star Citizen",
        slug="21287",
        channel="Transmission",
        category="Undefined",
        series="None",
        content=SAMPLE_CONTENT,
        rsi_url=rsi_url,
        web_url=None,
        published_at="2026-08-10T23:00:00+00:00",
    )


def test_build_schedule_embed_layout():
    from src.commands.twisc import build_schedule_embed

    days = parse_schedule(SAMPLE_CONTENT)
    embed = build_schedule_embed(_comm_link(), days)

    assert embed.title == "The Weekly Community Content Schedule"
    assert embed.url == "https://robertsspaceindustries.com/comm-link/transmission/21287"
    assert embed.colour is not None and embed.colour.value == 0x0099D6
    assert len(embed.fields) == 5
    assert embed.fields[0].name == "Monday, August 10, 2026"
    assert embed.fields[0].value == "- This Week in Star Citizen"
    assert embed.fields[1].value == (
        "- August 2026 Monthly Bundle\n- Maintenance: Issue Council, starting at 13:00 UTC"
    )
    assert all(not field.inline for field in embed.fields)
    assert embed.footer.text == "https://robertsspaceindustries.com/comm-link/transmission/21287"


def test_build_schedule_embed_without_url():
    from src.commands.twisc import build_schedule_embed

    embed = build_schedule_embed(_comm_link(rsi_url=None), parse_schedule(SAMPLE_CONTENT))
    assert embed.url is None
    assert embed.footer.text is None


def _cog_with(latest, subscriptions, last_posted_id):
    from src.commands.twisc import TwiscCog

    bot = MagicMock()
    bot.comm_links_api.search = AsyncMock(return_value=[latest] if latest else [])
    bot.state.set = AsyncMock()
    cog = TwiscCog(bot)
    cog.subscriptions = subscriptions
    cog.last_posted_id = last_posted_id
    return cog


async def test_first_poll_records_id_without_posting():
    link = _comm_link()
    cog = _cog_with(link, subscriptions=[{"discord_channel_id": 1, "guild_id": 2}], last_posted_id=None)
    await cog._check_latest()
    assert cog.last_posted_id == 21287
    cog.bot.get_channel.assert_not_called()
    cog.bot.state.set.assert_awaited_once()


async def test_poll_posts_new_comm_link_to_subscribed_channels():
    link = _comm_link()
    cog = _cog_with(link, subscriptions=[{"discord_channel_id": 1, "guild_id": 2}], last_posted_id=21278)
    channel = MagicMock()
    channel.send = AsyncMock()
    cog.bot.get_channel.return_value = channel
    await cog._check_latest()
    channel.send.assert_awaited_once()
    assert channel.send.await_args.kwargs["embed"].title == "The Weekly Community Content Schedule"
    assert cog.last_posted_id == 21287


async def test_poll_skips_already_posted_comm_link():
    link = _comm_link()
    cog = _cog_with(link, subscriptions=[{"discord_channel_id": 1, "guild_id": 2}], last_posted_id=21287)
    await cog._check_latest()
    cog.bot.get_channel.assert_not_called()
    cog.bot.state.set.assert_not_awaited()


async def test_poll_without_subscriptions_does_nothing():
    cog = _cog_with(_comm_link(), subscriptions=[], last_posted_id=None)
    await cog._check_latest()
    cog.bot.comm_links_api.search.assert_not_awaited()


async def test_poll_continues_past_per_channel_send_failure():
    link = _comm_link()
    cog = _cog_with(
        link,
        subscriptions=[
            {"discord_channel_id": 1, "guild_id": 2},
            {"discord_channel_id": 3, "guild_id": 2},
        ],
        last_posted_id=21278,
    )
    failing_channel = MagicMock()
    failing_channel.send = AsyncMock(side_effect=RuntimeError("boom"))
    ok_channel = MagicMock()
    ok_channel.send = AsyncMock()
    cog.bot.get_channel.side_effect = lambda channel_id: {1: failing_channel, 3: ok_channel}[channel_id]

    await cog._check_latest()

    ok_channel.send.assert_awaited_once()
    assert ok_channel.send.await_args.kwargs["embed"].title == "The Weekly Community Content Schedule"
    assert cog.last_posted_id == 21287
    cog.bot.state.set.assert_awaited_once()
