"""Client for the Ghosts of Klescher site's bot API (https://ghostsofklescher.org).

The site decides member and officer access from the Discord role IDs it is
sent, so the bot only reports raw roles, display names and avatar hashes. A
push that includes a name also adds a member the site has not seen yet.
"""

from __future__ import annotations

import aiohttp

MemberPayload = dict[str, str | list[str] | None]

_TIMEOUT = aiohttp.ClientTimeout(total=30)


class GokSiteClient:
    def __init__(self, base_url: str, token: str) -> None:
        self._members_url = f"{base_url.rstrip('/')}/api/bot/members"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._session: aiohttp.ClientSession | None = None

    async def update_member(self, member: MemberPayload) -> int:
        body = {key: value for key, value in member.items() if key != "id"}
        return await self._request("PUT", f"{self._members_url}/{member['id']}", body)

    async def remove_member(self, member_id: int | str) -> int:
        return await self._request("DELETE", f"{self._members_url}/{member_id}")

    async def sync_roster(self, members: list[MemberPayload]) -> int:
        return await self._request("PUT", self._members_url, {"members": members})

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, url: str, body: dict | None = None) -> int:
        if self._session is None:
            self._session = aiohttp.ClientSession(headers=self._headers, timeout=_TIMEOUT)
        async with self._session.request(method, url, json=body, raise_for_status=True) as response:
            data = await response.json()
        return data["updated"]
