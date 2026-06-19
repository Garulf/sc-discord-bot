"""A tiny client for the RSI status RSS feed.

Feed: https://status.robertsspaceindustries.com/index.xml (RSS 2.0). Each
``<item>`` is an incident with a stable ``guid`` and a ``pubDate`` that changes
when the incident is updated, so callers can detect both new incidents and
updates by comparing ``guid -> published``.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from xml.etree import ElementTree

import aiohttp

STATUS_FEED_URL = "https://status.robertsspaceindustries.com/index.xml"
STATUS_JSON_URL = "https://status.robertsspaceindustries.com/index.json"
STATUS_PAGE_URL = "https://status.robertsspaceindustries.com/"
USER_AGENT = "sc-discord-bot (+https://status.robertsspaceindustries.com)"
DEFAULT_TIMEOUT_SECONDS = 15

_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class StatusEntry:
    guid: str
    title: str
    link: str | None
    published: str | None
    summary: str | None

    @classmethod
    def from_item(cls, item: ElementTree.Element) -> StatusEntry:
        return cls(
            guid=_text(item, "guid") or _text(item, "link") or "",
            title=_text(item, "title") or "Untitled",
            link=_text(item, "link"),
            published=_text(item, "pubDate"),
            summary=_clean(_text(item, "description")),
        )


def _text(item: ElementTree.Element, tag: str) -> str | None:
    element = item.find(tag)
    if element is None or element.text is None:
        return None
    return element.text.strip()


def _clean(raw: str | None) -> str | None:
    if not raw:
        return None
    stripped = _TAG_RE.sub(" ", html.unescape(raw))
    collapsed = " ".join(stripped.split())
    return collapsed or None


async def fetch_status_entries(
    url: str = STATUS_FEED_URL, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> list[StatusEntry]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, text/xml"}
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(headers=headers, timeout=client_timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            body = await response.text()
    root = ElementTree.fromstring(body)
    return [StatusEntry.from_item(item) for item in root.findall("./channel/item")]


@dataclass(frozen=True)
class UnresolvedIssue:
    title: str
    link: str | None
    severity: str | None


@dataclass(frozen=True)
class StatusSystem:
    name: str
    status: str
    unresolved: list[UnresolvedIssue]


@dataclass(frozen=True)
class StatusOverview:
    summary_status: str
    systems: list[StatusSystem]


async def fetch_status_overview(
    url: str = STATUS_JSON_URL, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> StatusOverview:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(headers=headers, timeout=client_timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            payload = await response.json(content_type=None)

    systems = []
    for raw in payload.get("systems", []):
        if not isinstance(raw, dict):
            continue
        issues = [
            UnresolvedIssue(
                title=issue.get("title") or "Issue",
                link=issue.get("permalink"),
                severity=issue.get("severity"),
            )
            for issue in raw.get("unresolvedIssues", [])
            if isinstance(issue, dict)
        ]
        systems.append(
            StatusSystem(
                name=raw.get("name") or "Unknown",
                status=raw.get("status") or "unknown",
                unresolved=issues,
            )
        )
    return StatusOverview(summary_status=payload.get("summaryStatus") or "unknown", systems=systems)
