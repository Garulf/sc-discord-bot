"""Unit tests for the generic WikiResource base and extract_data helper.

Drives get/search/find against an in-memory fake client so the shared resource
behaviour is locked in without any HTTP calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.starcitizenwiki_api._common import (
    MAX_PAGE_SIZE,
    SEARCH_OVERFETCH_FACTOR,
    WikiResource,
    extract_data,
)
from src.starcitizenwiki_api.client import NotFoundError
from src.starcitizenwiki_api.weapons import Weapon, Weapons


@dataclass(frozen=True)
class _Thing:
    name: str
    slug: str | None

    @classmethod
    def from_api(cls, data: dict[str, Any], locale: str = "en_EN") -> _Thing:
        return cls(name=data.get("name") or "Unknown", slug=data.get("slug"))


class _FakeClient:
    """Serves a single-record payload by slug and a fixed listing for searches."""

    def __init__(self, *, single: dict | None = None, listing: list | None = None) -> None:
        self.single = single or {}
        self.listing = listing or []
        self.calls: list[tuple[str, dict | None]] = []

    async def get(self, path: str, *, params: dict | None = None, cache_ttl: float | None = None) -> Any:
        self.calls.append((path, params))
        if "/" in path:
            _, _, slug = path.partition("/")
            data = self.single.get(slug)
            return {"data": data} if data is not None else {}
        return {"data": list(self.listing)}


class _Things(WikiResource[_Thing]):
    endpoint = "things"
    model = _Thing
    noun = "thing"


# ── extract_data ──────────────────────────────────────────────────────────────


class TestExtractData:
    def test_returns_data_field(self):
        assert extract_data({"data": [1, 2]}) == [1, 2]

    def test_missing_data_returns_default(self):
        assert extract_data({}) is None
        assert extract_data({}, []) == []

    def test_non_dict_returns_default(self):
        assert extract_data("nope") is None
        assert extract_data(None, []) == []


# ── get ───────────────────────────────────────────────────────────────────────


class TestGet:
    async def test_returns_parsed_model(self):
        client = _FakeClient(single={"aurora": {"name": "Aurora", "slug": "aurora"}})
        thing = await _Things(client).get("aurora")
        assert thing == _Thing(name="Aurora", slug="aurora")

    async def test_missing_raises_not_found(self):
        with pytest.raises(NotFoundError):
            await _Things(_FakeClient()).get("ghost")

    async def test_strips_whitespace_from_identifier(self):
        client = _FakeClient(single={"aurora": {"name": "Aurora", "slug": "aurora"}})
        await _Things(client).get("  aurora  ")
        assert client.calls[0][0] == "things/aurora"


# ── search ────────────────────────────────────────────────────────────────────


class TestSearch:
    async def test_blank_query_calls_api_without_name_filter(self):
        client = _FakeClient()
        await _Things(client).search("   ")
        assert len(client.calls) == 1
        assert "filter[name]" not in client.calls[0][1]

    async def test_deduplicates_by_slug(self):
        listing = [
            {"name": "Aurora", "slug": "aurora"},
            {"name": "Aurora v2", "slug": "aurora"},
            {"name": "Cutlass", "slug": "cutlass"},
        ]
        results = await _Things(_FakeClient(listing=listing)).search("a")
        assert [t.slug for t in results] == ["aurora", "cutlass"]

    async def test_respects_limit(self):
        listing = [{"name": f"n{i}", "slug": f"s{i}"} for i in range(10)]
        results = await _Things(_FakeClient(listing=listing)).search("n", limit=3)
        assert len(results) == 3

    async def test_overfetches_page_size_capped(self):
        client = _FakeClient(listing=[])
        await _Things(client).search("x", limit=25)
        params = client.calls[0][1]
        assert params["page[size]"] == min(25 * SEARCH_OVERFETCH_FACTOR, MAX_PAGE_SIZE)


# ── find ──────────────────────────────────────────────────────────────────────


class TestFind:
    async def test_no_results_returns_none(self):
        assert await _Things(_FakeClient(listing=[])).find("anything") is None

    async def test_exact_name_is_preferred_and_refetched_by_slug(self):
        listing = [
            {"name": "Aurora", "slug": "aurora"},
            {"name": "Aurora MR", "slug": "aurora-mr"},
        ]
        single = {"aurora": {"name": "Aurora FULL", "slug": "aurora"}}
        result = await _Things(_FakeClient(single=single, listing=listing)).find("Aurora")
        assert result.name == "Aurora FULL"  # came from the re-fetch, not the listing

    async def test_falls_back_to_summary_when_refetch_missing(self):
        listing = [{"name": "Aurora MR", "slug": "aurora-mr"}]
        result = await _Things(_FakeClient(single={}, listing=listing)).find("Aurora MR")
        assert result == _Thing(name="Aurora MR", slug="aurora-mr")


# ── Weapons._pick_best override ───────────────────────────────────────────────


class TestWeaponsPickBest:
    def _weapon(self, name: str) -> Weapon:
        return Weapon.from_api({"name": name})

    def test_prefers_exact_name_match(self):
        results = [self._weapon('A03 "Canuto" Sniper Rifle'), self._weapon("A03 Sniper Rifle")]
        chosen = Weapons(_FakeClient())._pick_best(results, "A03 Sniper Rifle")
        assert chosen.name == "A03 Sniper Rifle"

    def test_prefers_base_model_over_skin_when_no_exact_match(self):
        results = [self._weapon('A03 "Canuto" Sniper Rifle'), self._weapon("A03 Sniper Rifle")]
        chosen = Weapons(_FakeClient())._pick_best(results, "sniper")
        assert chosen.name == "A03 Sniper Rifle"

    def test_falls_back_to_first_when_all_are_skins(self):
        results = [self._weapon('A "X" Rifle'), self._weapon('A "Y" Rifle')]
        chosen = Weapons(_FakeClient())._pick_best(results, "rifle")
        assert chosen.name == 'A "X" Rifle'
