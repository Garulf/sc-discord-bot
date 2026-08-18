"""RSI devtracker feed: fetch and parse https://robertsspaceindustries.com/en/community/devtracker.

The devtracker API returns rendered HTML fragments rather than structured
data, so this module parses the fragment with the stdlib HTML parser.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from html.parser import HTMLParser

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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        css = (attributes.get("class") or "").split()
        if tag == "a" and "devpost" in css:
            self._current = {"href": attributes.get("href") or ""}
            return
        if self._current is None:
            return
        if tag == "img" and "avatar_url" not in self._current:
            self._current["avatar_url"] = attributes.get("src")
            return
        for css_class, field in self._TEXT_CLASSES.items():
            if css_class in css:
                self._text_field = field
                self._current.setdefault(field, "")
                return

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._text_field is not None:
            self._current[self._text_field] += data

    def handle_endtag(self, tag: str) -> None:
        if tag in ("div", "span", "p"):
            self._text_field = None
        elif tag == "a" and self._current is not None:
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
