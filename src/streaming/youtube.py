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
_RSS_CHECK_LIMIT = 3  # only check the 3 most recent videos per poll


class _QuotaExceeded(Exception):
    pass


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
        # Already a channel ID — skip API, display name will be filled in on first live detection
        if re.fullmatch(r"UC[\w-]{22}", cleaned):
            return (cleaned, cleaned)
        # Handle format: @username or channel/username
        handle = cleaned.lstrip("@").removeprefix("channel/")
        session = await self._get_session()

        # Try forHandle first (modern @handle), then forUsername (legacy)
        for param_key, param_val in (("forHandle", f"@{handle}"), ("forUsername", handle)):
            try:
                async with session.get(
                    _CHANNELS_URL,
                    params={"part": "id,snippet", param_key: param_val, "key": self._api_key},
                ) as r:
                    r.raise_for_status()
                    data = await r.json()
            except aiohttp.ClientError as exc:
                logger.warning("YouTube channel lookup error (%s=%s): %s", param_key, param_val, exc)
                continue  # try the next lookup param before giving up
            items = data.get("items", [])
            if items:
                item = items[0]
                return item["id"], item["snippet"]["title"]
            logger.debug("YouTube %s=%s returned no items", param_key, param_val)

        return None

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

    async def _live_page_video_id(self, channel_id: str) -> str | None:
        """Scrape the channel /live page to find the active live video ID.

        YouTube doesn't include spontaneous (non-scheduled) streams in the RSS
        feed, so this is the only free way to detect them.
        """
        session = await self._get_session()
        try:
            async with session.get(
                f"https://www.youtube.com/channel/{channel_id}/live",
                headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
            ) as r:
                if r.status != 200:
                    return None
                text = await r.text()
        except aiohttp.ClientError as exc:
            logger.debug("YouTube live page fetch error for %s: %s", channel_id, exc)
            return None

        if '"isLive":true' not in text:
            return None
        m = re.search(r'"videoId":"([\w-]{11})"', text)
        return m.group(1) if m else None

    async def _check_video_live(self, video_id: str, channel_display: str) -> StreamInfo | None:
        """Return StreamInfo if the video is currently live, else None.

        Raises _QuotaExceeded if the API key is out of quota so the caller
        can abort the poll cycle instead of spamming further requests.
        """
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
                if r.status == 403:
                    body = await r.json()
                    reason = body.get("error", {}).get("errors", [{}])[0].get("reason", "")
                    if reason == "quotaExceeded":
                        raise _QuotaExceeded()
                r.raise_for_status()
                data = await r.json()
        except _QuotaExceeded:
            raise
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
            channel_name=snippet.get("channelTitle") or channel_display or "",
            stream_url=f"https://www.youtube.com/watch?v={video_id}",
            title=snippet.get("title", ""),
            thumbnail_url=snippet.get("thumbnails", {}).get("maxres", {}).get("url")
            or snippet.get("thumbnails", {}).get("high", {}).get("url"),
            viewer_count=viewers,
        )

    async def get_stream(
        self, channel_id: str, channel_display: str, known_live_video_id: str | None
    ) -> StreamInfo | None:
        """Return StreamInfo if channel is live, else None."""
        if not self._configured:
            return None

        try:
            # Re-check an ongoing stream first (1 API unit)
            if known_live_video_id:
                info = await self._check_video_live(known_live_video_id, channel_display)
                if info:
                    return info
                # Stream ended — fall through to check RSS for a new one

            # Check only the most recent RSS videos (scheduled streams appear here)
            video_ids = await self._rss_video_ids(channel_id)
            for vid in video_ids[:_RSS_CHECK_LIMIT]:
                if vid == known_live_video_id:
                    continue
                info = await self._check_video_live(vid, channel_display)
                if info:
                    return info

            # Fallback: scrape /live page to catch spontaneous (non-scheduled) streams
            live_vid = await self._live_page_video_id(channel_id)
            if live_vid and live_vid != known_live_video_id:
                info = await self._check_video_live(live_vid, channel_display)
                if info:
                    return info

        except _QuotaExceeded:
            logger.warning("YouTube API quota exceeded — skipping poll cycle for %s", channel_id)

        return None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
