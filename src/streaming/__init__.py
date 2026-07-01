"""Platform clients for detecting live streams."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StreamInfo:
    platform: str  # "twitch" | "youtube" | "tiktok"
    stream_id: str  # unique ID for dedup
    channel_name: str
    stream_url: str
    title: str
    game_or_category: str | None = None
    viewer_count: int | None = None
    thumbnail_url: str | None = None


from src.streaming.tiktok import TikTokClient  # noqa: E402
from src.streaming.twitch import TwitchClient  # noqa: E402
from src.streaming.youtube import YouTubeClient  # noqa: E402

__all__ = ["StreamInfo", "TwitchClient", "YouTubeClient", "TikTokClient"]
