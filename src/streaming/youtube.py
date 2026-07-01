"""YouTube live stream detection via RSS feed + Data API v3."""

from __future__ import annotations

import logging
import re

import aiohttp

from src.streaming import StreamInfo

logger = logging.getLogger(__name__)

_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_RSS_URL = "https://www.youtube.com/feeds/videos.xml"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class YouTubeClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._session: aiohttp.ClientSession | None = None

        if not api_key:
            logger.warning("YOUTUBE_API_KEY not set — YouTube integration disabled")

    @property
    def _configured(self) -> bool:
        return bool(self._api_key)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_TIMEOUT)
        return self._session

    async def resolve_channel(self, input_str: str) -> tuple[str, str] | None:
        """Return (channel_id, display_name) from a handle, URL, or channel ID."""
        if not self._configured:
            return None
        # Strip URL prefix
        cleaned = re.sub(r"https?://(?:www\.)?youtube\.com/", "", input_str).strip("/")
        # Already a channel ID
        if cleaned.startswith("UC") and len(cleaned) == 24:
            channel_id = cleaned
            name = await self._channel_name(channel_id)
            return (channel_id, name) if name else None
        # Handle format: @username or channel/username
        handle = cleaned.lstrip("@").removeprefix("channel/")
        session = await self._get_session()
        try:
            async with session.get(
                _CHANNELS_URL,
                params={"part": "id,snippet", "forHandle": f"@{handle}", "key": self._api_key},
            ) as r:
                r.raise_for_status()
                data = await r.json()
        except aiohttp.ClientError as exc:
            logger.warning("YouTube channel lookup error: %s", exc)
            return None
        items = data.get("items", [])
        if not items:
            return None
        item = items[0]
        return item["id"], item["snippet"]["title"]

    async def _channel_name(self, channel_id: str) -> str | None:
        session = await self._get_session()
        try:
            async with session.get(
                _CHANNELS_URL,
                params={"part": "snippet", "id": channel_id, "key": self._api_key},
            ) as r:
                r.raise_for_status()
                data = await r.json()
        except aiohttp.ClientError as exc:
            logger.warning("YouTube channel name lookup error: %s", exc)
            return None
        items = data.get("items", [])
        return items[0]["snippet"]["title"] if items else None

    async def _rss_video_ids(self, channel_id: str) -> list[str]:
        """Fetch latest video IDs from the channel RSS feed (free, no quota)."""
        session = await self._get_session()
        try:
            async with session.get(_RSS_URL, params={"channel_id": channel_id}) as r:
                if r.status != 200:
                    return []
                text = await r.text()
        except aiohttp.ClientError as exc:
            logger.warning("YouTube RSS fetch error for %s: %s", channel_id, exc)
            return []
        return re.findall(r"<yt:videoId>([^<]+)</yt:videoId>", text)

    async def _check_video_live(self, video_id: str, channel_display: str) -> StreamInfo | None:
        """Return StreamInfo if the video is currently live, else None."""
        session = await self._get_session()
        try:
            async with session.get(
                _VIDEOS_URL,
                params={
                    "part": "snippet,liveStreamingDetails",
                    "id": video_id,
                    "key": self._api_key,
                },
            ) as r:
                r.raise_for_status()
                data = await r.json()
        except aiohttp.ClientError as exc:
            logger.warning("YouTube video check error: %s", exc)
            return None
        items = data.get("items", [])
        if not items:
            return None
        item = items[0]
        live = item.get("liveStreamingDetails", {})
        # Live if actualStartTime is set and concurrentViewers is present
        if not live.get("actualStartTime") or "concurrentViewers" not in live:
            return None
        snippet = item.get("snippet", {})
        try:
            viewers = int(live["concurrentViewers"])
        except (ValueError, TypeError):
            viewers = None
        return StreamInfo(
            platform="youtube",
            stream_id=video_id,
            channel_name=channel_display or snippet.get("channelTitle", ""),
            stream_url=f"https://www.youtube.com/watch?v={video_id}",
            title=snippet.get("title", ""),
            thumbnail_url=snippet.get("thumbnails", {}).get("maxres", {}).get("url")
            or snippet.get("thumbnails", {}).get("high", {}).get("url"),
            viewer_count=viewers,
        )

    async def get_stream(
        self, channel_id: str, channel_display: str, known_live_video_id: str | None
    ) -> StreamInfo | None:
        """Return StreamInfo if channel is live, else None.

        Pass known_live_video_id so we can re-check an existing stream's status
        and detect when it ends, without burning RSS quota on every poll.
        """
        if not self._configured:
            return None

        # Re-check an ongoing stream first (cheap: 1 API unit)
        if known_live_video_id:
            info = await self._check_video_live(known_live_video_id, channel_display)
            if info:
                return info
            # Stream ended — fall through to check RSS for a new one

        # Check RSS for new video IDs
        video_ids = await self._rss_video_ids(channel_id)
        for vid in video_ids:
            if vid == known_live_video_id:
                continue  # already checked above
            info = await self._check_video_live(vid, channel_display)
            if info:
                return info
        return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
