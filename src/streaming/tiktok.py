"""TikTok live stream detection via best-effort HTML scraping.

TikTok has no public API for live status. This module scrapes the profile
page and looks for live-room data in the embedded JSON. It may break if
TikTok changes their page structure or if Cloudflare blocks the request.
"""

from __future__ import annotations

import json
import logging
import re

import aiohttp

from src.streaming import StreamInfo

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=15)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class TikTokClient:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT)
        return self._session

    async def get_stream(self, username: str) -> StreamInfo | None:
        session = await self._get_session()
        url = f"https://www.tiktok.com/@{username.lstrip('@')}"
        try:
            async with session.get(url) as r:
                if r.status == 404:
                    return None
                if r.status != 200:
                    logger.warning("TikTok fetch returned %s for @%s", r.status, username)
                    return None
                html = await r.text()
        except aiohttp.ClientError as exc:
            logger.warning("TikTok scrape error for @%s: %s", username, exc)
            return None

        # Extract the embedded JSON blob
        m = re.search(r'id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>([^<]+)<', html)
        if not m:
            logger.debug("TikTok: could not find rehydration JSON for @%s (may be Cloudflare-blocked)", username)
            return None

        try:
            blob = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.debug("TikTok: failed to parse rehydration JSON for @%s", username)
            return None

        # Drill into the nested structure to find live room info
        # Path varies; search recursively for liveRoom key
        live_room = _find_key(blob, "liveRoom")
        if not live_room or not isinstance(live_room, dict):
            return None

        # Confirm actually live
        status = live_room.get("status") or live_room.get("statusStr", "")
        if "live" not in str(status).lower() and live_room.get("liveRoomMode") is None:
            return None

        room_id = str(live_room.get("roomId") or live_room.get("id") or "live")
        title = live_room.get("title") or f"@{username} is live"
        viewer_count = live_room.get("userCount") or live_room.get("viewerCount")

        return StreamInfo(
            platform="tiktok",
            stream_id=room_id,
            channel_name=username,
            stream_url=f"https://www.tiktok.com/@{username.lstrip('@')}/live",
            title=title,
            viewer_count=viewer_count,
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


def _find_key(obj, key: str):
    """Recursively search a nested dict/list for the first value at `key`."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            result = _find_key(v, key)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_key(item, key)
            if result is not None:
                return result
    return None
