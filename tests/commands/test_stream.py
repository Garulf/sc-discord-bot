from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.stream import StreamCog, build_ended_message, build_live_message
from src.streaming import StreamInfo


def test_build_live_message_includes_icon_and_url():
    stream = StreamInfo(
        platform="youtube",
        stream_id="abc123",
        channel_name="Garulf",
        stream_url="https://www.youtube.com/watch?v=abc123",
        title="Some Title",
    )
    msg = build_live_message(stream)
    assert msg == "🔴 **Garulf** is LIVE on YouTube!\nhttps://www.youtube.com/watch?v=abc123"


def test_build_ended_message_drops_icon_and_url():
    msg = build_ended_message("Garulf", "youtube")
    assert msg == "Garulf was live on YouTube"
    assert "🔴" not in msg


def _cog() -> StreamCog:
    bot = MagicMock()
    cog = StreamCog.__new__(StreamCog)
    cog.bot = bot
    cog.youtube = MagicMock()
    cog.twitch = MagicMock()
    cog.tiktok = MagicMock()
    return cog


@pytest.mark.asyncio
async def test_check_sub_edits_notification_when_stream_ends():
    cog = _cog()
    cog.youtube.get_stream = AsyncMock(return_value=None)

    message = MagicMock()
    message.edit = AsyncMock()
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=message)
    cog.bot.get_channel = MagicMock(return_value=channel)

    sub = {
        "platform": "youtube",
        "channel_login": "UCabc",
        "channel_display": "Garulf",
        "discord_channel_id": 123,
        "live_id": "abc123",
        "notification_message_id": 999,
    }

    changed = await cog._check_sub(sub)

    assert changed is True
    assert sub["live_id"] is None
    channel.fetch_message.assert_awaited_once_with(999)
    message.edit.assert_awaited_once_with(content="Garulf was live on YouTube")
