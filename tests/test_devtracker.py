from unittest.mock import AsyncMock, MagicMock

from src.rsi_devtracker import DevPost


def _post(post_id: int, **overrides) -> DevPost:
    defaults = dict(
        post_id=post_id,
        url=f"https://robertsspaceindustries.com/spectrum/community/SC/forum/1/thread/t/{post_id}",
        author="Wakapedia-CIG",
        avatar_url="https://robertsspaceindustries.com/media/avatar.png",
        category="Patch Notes",
        thread="[All Waves] 4.10 PTU Patch Notes",
        details="Patch released!",
    )
    defaults.update(overrides)
    return DevPost(**defaults)


def _cog_with(posts, subscriptions, seen_ids):
    from src.commands.devtracker import DevTrackerCog

    bot = MagicMock()
    bot.state.set = AsyncMock()
    cog = DevTrackerCog(bot)
    cog.client = MagicMock()
    cog.client.fetch_posts = AsyncMock(return_value=posts)
    cog.subscriptions = subscriptions
    cog.seen_ids = seen_ids
    return cog


def test_build_devpost_embed_full_fields():
    from src.commands.devtracker import build_devpost_embed

    embed = build_devpost_embed(_post(9086979))
    assert embed.title == "[All Waves] 4.10 PTU Patch Notes"
    assert embed.url.endswith("/9086979")
    assert embed.description == "Patch released!"
    assert embed.author.name == "Wakapedia-CIG"
    assert embed.author.icon_url == "https://robertsspaceindustries.com/media/avatar.png"
    assert embed.footer.text == "Patch Notes"
    assert embed.colour.value == 0x0099D6
    assert embed.timestamp is not None


def test_build_devpost_embed_truncates_long_fields():
    from src.commands.devtracker import build_devpost_embed

    embed = build_devpost_embed(_post(1, thread="T" * 300, details="D" * 5000))
    assert len(embed.title) == 256
    assert len(embed.description) == 4096


def test_build_devpost_embed_missing_optionals():
    from src.commands.devtracker import build_devpost_embed

    embed = build_devpost_embed(_post(1, thread=None, details=None, category=None, avatar_url=None))
    assert embed.title == "Dev Tracker Post"
    assert embed.description is None
    assert embed.footer.text is None


async def test_first_poll_records_id_without_posting():
    cog = _cog_with([_post(100), _post(99)], [{"discord_channel_id": 1, "guild_id": 2}], [])
    await cog._check_latest()
    assert sorted(cog.seen_ids) == [99, 100]
    cog.bot.get_channel.assert_not_called()
    cog.bot.state.set.assert_awaited_once()


async def test_poll_posts_new_posts_oldest_first():
    cog = _cog_with([_post(102), _post(101), _post(99)], [{"discord_channel_id": 1, "guild_id": 2}], [99, 100])
    channel = MagicMock()
    channel.send = AsyncMock()
    cog.bot.get_channel.return_value = channel
    await cog._check_latest()
    sent_ids = [call.kwargs["embed"].url.rsplit("/", 1)[-1] for call in channel.send.await_args_list]
    assert sent_ids == ["101", "102"]
    assert set(cog.seen_ids) == {99, 100, 101, 102}


async def test_poll_caps_backlog_at_ten_newest():
    posts = [_post(pid) for pid in range(120, 100, -1)]  # 20 new posts, newest first
    cog = _cog_with(posts, [{"discord_channel_id": 1, "guild_id": 2}], [100])
    channel = MagicMock()
    channel.send = AsyncMock()
    cog.bot.get_channel.return_value = channel
    await cog._check_latest()
    assert channel.send.await_count == 10
    first_sent = channel.send.await_args_list[0].kwargs["embed"].url.rsplit("/", 1)[-1]
    assert first_sent == "111"
    assert 120 in cog.seen_ids


async def test_poll_per_channel_failure_does_not_block_others():
    cog = _cog_with(
        [_post(101)],
        [{"discord_channel_id": 1, "guild_id": 2}, {"discord_channel_id": 3, "guild_id": 2}],
        [100],
    )
    bad = MagicMock()
    bad.send = AsyncMock(side_effect=RuntimeError("boom"))
    good = MagicMock()
    good.send = AsyncMock()
    cog.bot.get_channel.side_effect = lambda cid: {1: bad, 3: good}[cid]
    await cog._check_latest()
    good.send.assert_awaited_once()
    assert 101 in cog.seen_ids
    cog.bot.state.set.assert_awaited_once()


async def test_poll_without_subscriptions_does_not_fetch():
    cog = _cog_with([_post(101)], [], [100])
    await cog._check_latest()
    cog.client.fetch_posts.assert_not_awaited()


async def test_poll_with_no_parseable_posts_keeps_state():
    cog = _cog_with([], [{"discord_channel_id": 1, "guild_id": 2}], [100])
    await cog._check_latest()
    assert cog.seen_ids == [100]
    cog.bot.state.set.assert_not_awaited()


async def test_poll_dedupes_by_id_not_watermark_inversion():
    # Regression: the feed is ordered by tracker date, not post id, so an id-lower
    # post can appear above id-higher posts that were already seen.
    cog = _cog_with(
        [_post(200), _post(150), _post(199)],
        [{"discord_channel_id": 1, "guild_id": 2}],
        [199, 200],
    )
    channel = MagicMock()
    channel.send = AsyncMock()
    cog.bot.get_channel.return_value = channel
    await cog._check_latest()
    sent_ids = [call.kwargs["embed"].url.rsplit("/", 1)[-1] for call in channel.send.await_args_list]
    assert sent_ids == ["150"]
    assert set(cog.seen_ids) == {150, 199, 200}


async def test_post_command_sends_latest_and_leaves_seen_ids_unchanged():
    cog = _cog_with([_post(300), _post(299)], [], [299])
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    await cog.post.callback(cog, interaction)
    interaction.response.defer.assert_awaited_once()
    embed = interaction.followup.send.await_args.kwargs["embed"]
    assert embed.url.endswith("/300")
    assert cog.seen_ids == [299]
    cog.bot.state.set.assert_not_awaited()


async def test_post_command_reports_fetch_failure():
    cog = _cog_with([], [], [299])
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    await cog.post.callback(cog, interaction)
    msg = interaction.followup.send.await_args.args[0]
    assert "could not" in msg.lower()
