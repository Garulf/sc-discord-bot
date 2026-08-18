"""RSI devtracker feed: fetch and parse https://robertsspaceindustries.com/en/community/devtracker.

The devtracker API returns rendered HTML fragments rather than structured
data, so this module parses the fragment with the stdlib HTML parser.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from html.parser import HTMLParser

import aiohttp

logger = logging.getLogger(__name__)

RSI_BASE = "https://robertsspaceindustries.com"


@dataclass(frozen=True)
class DevPost:
    post_id: int
    url: str
    author: str
    avatar_url: str | None
    category: str | None
    thread: str | None
    details: str | None


class _DevPostHTMLParser(HTMLParser):
    """Collects one dict per ``<a class="devpost">`` block from the fragment."""

    _TEXT_CLASSES = {"nickname": "author", "category": "category", "thread": "thread", "details": "details"}

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[dict] = []
        self._current: dict | None = None
        self._text_field: str | None = None
        self._field_tag: str | None = None
        self._field_depth: int = 0
        self._anchor_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        css = (attributes.get("class") or "").split()
        if tag == "a" and "devpost" in css:
            self._current = {"href": attributes.get("href") or ""}
            self._anchor_depth = 1
            return
        if self._current is None:
            return
        if tag == "a":
            self._anchor_depth += 1
        if self._text_field is not None and tag == self._field_tag:
            self._field_depth += 1
            return
        if tag == "img" and "avatar_url" not in self._current:
            self._current["avatar_url"] = attributes.get("src")
            return
        for css_class, field in self._TEXT_CLASSES.items():
            if css_class in css:
                self._text_field = field
                self._field_tag = tag
                self._field_depth = 1
                self._current.setdefault(field, "")
                return

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._text_field is not None:
            self._current[self._text_field] += data

    def handle_endtag(self, tag: str) -> None:
        if self._text_field is not None and tag == self._field_tag:
            self._field_depth -= 1
            if self._field_depth == 0:
                self._text_field = None
                self._field_tag = None
            return
        if tag == "a" and self._current is not None:
            self._anchor_depth -= 1
            if self._anchor_depth == 0:
                self.blocks.append(self._current)
                self._current = None


def parse_devposts(html: str) -> list[DevPost]:
    """Parse the devtracker HTML fragment into posts, newest first as served.

    Blocks without a numeric post id in the link are skipped; unparseable
    input yields an empty list so callers can skip the cycle.
    """
    parser = _DevPostHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed markup must not propagate
        logger.warning("Failed to parse devtracker HTML fragment")
        return []

    posts: list[DevPost] = []
    for block in parser.blocks:
        href = block.get("href", "")
        tail = href.rstrip("/").rsplit("/", 1)[-1]
        if not tail.isdigit():
            continue
        posts.append(
            DevPost(
                post_id=int(tail),
                url=RSI_BASE + href,
                author=(block.get("author") or "").strip() or "Unknown",
                avatar_url=block.get("avatar_url"),
                category=(block.get("category") or "").strip() or None,
                thread=(block.get("thread") or "").strip() or None,
                details=(block.get("details") or "").strip() or None,
            )
        )
    return posts


_API_URL = f"{RSI_BASE}/api/community/getTrackedPosts"
_TIMEOUT = aiohttp.ClientTimeout(total=15)
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


class DevTrackerClient:
    """Fetches the devtracker feed. The session is created lazily so it binds
    to the running event loop, mirroring the streaming clients."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=_HEADERS, timeout=_TIMEOUT)
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def fetch_posts(self) -> list[DevPost]:
        session = await self._get_session()
        try:
            async with session.post(_API_URL, json={"page": 1}) as response:
                if response.status != 200:
                    logger.warning("Devtracker fetch returned HTTP %s", response.status)
                    return []
                payload = await response.json()
        except (aiohttp.ClientError, ValueError) as exc:
            logger.warning("Devtracker fetch failed: %s", exc)
            return []

        if not isinstance(payload, dict) or payload.get("success") != 1:
            logger.warning("Devtracker API returned non-success payload")
            return []
        data = payload.get("data")
        if not isinstance(data, dict):
            logger.warning("Devtracker API returned unexpected data shape")
            return []
        html = data.get("html") or ""
        return parse_devposts(html)
