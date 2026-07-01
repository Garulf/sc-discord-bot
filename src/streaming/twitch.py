"""Twitch Helix API client for live stream detection."""

from __future__ import annotations

import logging

import aiohttp

from src.streaming import StreamInfo

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
_STREAMS_URL = "https://api.twitch.tv/helix/streams"
_USERS_URL = "https://api.twitch.tv/helix/users"
_TIMEOUT = aiohttp.ClientTimeout(total=10)


class TwitchClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

        if not client_id or not client_secret:
            logger.warning("TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET not set — Twitch integration disabled")

    @property
    def _configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_TIMEOUT)
        return self._session

    async def _auth(self) -> bool:
        session = await self._get_session()
        try:
            async with session.post(
                _TOKEN_URL,
                params={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "client_credentials",
                },
            ) as r:
                if r.status != 200:
                    logger.error("Twitch auth failed: %s", r.status)
                    return False
                data = await r.json()
                self._token = data.get("access_token")
                return bool(self._token)
        except aiohttp.ClientError as exc:
            logger.warning("Twitch auth error: %s", exc)
            return False

    def _headers(self) -> dict[str, str]:
        return {
            "Client-Id": self._client_id,
            "Authorization": f"Bearer {self._token}",
        }

    async def _get(self, url: str, params: dict) -> dict | None:
        """GET with automatic token refresh on 401."""
        if not self._token and not await self._auth():
            return None
        session = await self._get_session()
        try:
            async with session.get(url, headers=self._headers(), params=params) as r:
                if r.status == 401:
                    if not await self._auth():
                        return None
                    async with session.get(url, headers=self._headers(), params=params) as r2:
                        r2.raise_for_status()
                        return await r2.json()
                r.raise_for_status()
                return await r.json()
        except aiohttp.ClientError as exc:
            logger.warning("Twitch API error: %s", exc)
            return None

    async def get_stream(self, user_login: str) -> StreamInfo | None:
        if not self._configured:
            return None
        data = await self._get(_STREAMS_URL, {"user_login": user_login.lower()})
        if not data:
            return None
        streams = data.get("data", [])
        if not streams:
            return None
        s = streams[0]
        # Replace {width}x{height} template in thumbnail URL
        thumb = s.get("thumbnail_url", "").replace("{width}", "1280").replace("{height}", "720")
        return StreamInfo(
            platform="twitch",
            stream_id=s["id"],
            channel_name=s.get("user_name", user_login),
            stream_url=f"https://twitch.tv/{s.get('user_login', user_login)}",
            title=s.get("title", ""),
            game_or_category=s.get("game_name") or None,
            viewer_count=s.get("viewer_count"),
            thumbnail_url=thumb or None,
        )

    async def verify_user(self, user_login: str) -> str | None:
        """Return display name if the user exists, else None."""
        if not self._configured:
            return None
        data = await self._get(_USERS_URL, {"login": user_login.lower()})
        if not data:
            return None
        users = data.get("data", [])
        return users[0].get("display_name") if users else None

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
