from unittest.mock import AsyncMock, MagicMock

import pytest

from src.streaming.youtube import YouTubeClient


def _mock_session(payload: dict) -> MagicMock:
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value=payload)
    response.raise_for_status = MagicMock()

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    session.get = MagicMock(return_value=ctx)
    return session


def _videos_payload(*, live_broadcast_content: str, actual_end_time: str | None = None) -> dict:
    live_streaming_details = {}
    if actual_end_time is not None:
        live_streaming_details["actualEndTime"] = actual_end_time
    return {
        "items": [
            {
                "snippet": {
                    "liveBroadcastContent": live_broadcast_content,
                    "channelTitle": "Some Channel",
                    "title": "Some Title",
                },
                "liveStreamingDetails": live_streaming_details,
            }
        ]
    }


@pytest.mark.asyncio
async def test_check_video_live_reports_live_stream_as_live():
    client = YouTubeClient(api_key="key")
    client._get_session = AsyncMock(
        return_value=_mock_session(_videos_payload(live_broadcast_content="live"))
    )

    info = await client._check_video_live("abc123", "Some Channel")

    assert info is not None
    assert info.stream_id == "abc123"


@pytest.mark.asyncio
async def test_check_video_live_ignores_stale_live_flag_after_actual_end_time():
    """Regression test: YouTube's videos.list can keep reporting
    liveBroadcastContent="live" for a broadcast that has already ended
    (actualEndTime set). Treating that as still-live causes the poller to
    repeatedly flap the subscription between "ended" and "new stream",
    spamming duplicate live notifications for a stream that isn't live.
    """
    client = YouTubeClient(api_key="key")
    client._get_session = AsyncMock(
        return_value=_mock_session(
            _videos_payload(live_broadcast_content="live", actual_end_time="2026-08-27T18:05:00Z")
        )
    )

    info = await client._check_video_live("abc123", "Some Channel")

    assert info is None
