"""Unit tests for the generic UEX CatalogResource base.

Drives all/get/search/find against an in-memory fake client; no HTTP involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.uex_api._common import CatalogResource
from src.uex_api.client import NotFoundError


@dataclass(frozen=True)
class _Item:
    id: int | None
    name: str
    code: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> _Item:
        return cls(id=data.get("id"), name=data.get("name") or "", code=data.get("code"))


class _FakeClient:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict | None]] = []

    async def get(self, path: str, *, params: dict | None = None, cache_ttl: float | None = None) -> Any:
        self.calls.append((path, params))
        return list(self.rows)


class _Items(CatalogResource[_Item]):
    endpoint = "items"
    model = _Item
    noun = "item"

    def _haystack(self, item: _Item) -> str:
        return f"{item.name} {item.code or ''}".lower()

    def _exact_match(self, item: _Item, needle: str) -> bool:
        return item.name.lower() == needle or (item.code or "").lower() == needle


_ROWS = [
    {"id": 1, "name": "Gold", "code": "GOLD"},
    {"id": 2, "name": "Laranite", "code": "LARA"},
    {"id": 3, "name": "Golden Apples", "code": "APPL"},
    {"id": 4, "name": "Not a dict placeholder", "code": None},
]


class TestAll:
    async def test_parses_dict_rows_into_models(self):
        items = await _Items(_FakeClient(_ROWS)).all()
        assert [i.name for i in items] == ["Gold", "Laranite", "Golden Apples", "Not a dict placeholder"]

    async def test_ignores_non_dict_rows(self):
        items = await _Items(_FakeClient([{"id": 1, "name": "Gold"}, "junk", 42])).all()
        assert [i.name for i in items] == ["Gold"]


class TestGet:
    async def test_returns_item_by_id(self):
        item = await _Items(_FakeClient(_ROWS)).get(2)
        assert item.name == "Laranite"

    async def test_unknown_id_raises_not_found(self):
        with pytest.raises(NotFoundError):
            await _Items(_FakeClient(_ROWS)).get(999)


class TestSearch:
    async def test_blank_query_returns_empty(self):
        assert await _Items(_FakeClient(_ROWS)).search("  ") == []

    async def test_matches_on_name_substring(self):
        results = await _Items(_FakeClient(_ROWS)).search("gold")
        assert {i.name for i in results} == {"Gold", "Golden Apples"}

    async def test_matches_on_code(self):
        results = await _Items(_FakeClient(_ROWS)).search("lara")
        assert [i.name for i in results] == ["Laranite"]

    async def test_respects_limit(self):
        results = await _Items(_FakeClient(_ROWS)).search("gold", limit=1)
        assert len(results) == 1


class TestFind:
    async def test_exact_name_wins_over_substring(self):
        item = await _Items(_FakeClient(_ROWS)).find("Gold")
        assert item is not None and item.name == "Gold"

    async def test_matches_exact_code(self):
        item = await _Items(_FakeClient(_ROWS)).find("LARA")
        assert item is not None and item.name == "Laranite"

    async def test_falls_back_to_first_result(self):
        item = await _Items(_FakeClient(_ROWS)).find("golden")
        assert item is not None and item.name == "Golden Apples"

    async def test_no_match_returns_none(self):
        assert await _Items(_FakeClient(_ROWS)).find("zzz") is None


class TestDefaultMatching:
    """A subclass that does not override the matching hooks uses name only."""

    class _NameOnly(CatalogResource[_Item]):
        endpoint = "items"
        model = _Item
        noun = "item"

    async def test_default_haystack_and_exact_match_use_name(self):
        resource = self._NameOnly(_FakeClient(_ROWS))
        assert [i.name for i in await resource.search("gold")] == ["Gold", "Golden Apples"]
        assert (await resource.find("gold")).name == "Gold"
