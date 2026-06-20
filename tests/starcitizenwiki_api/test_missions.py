"""Unit tests for Mission.from_api — covers the two bugs fixed in 5069c68:

1. rank_label is resolved from faction.reputation_ladder.standings[rank_index]
2. Blueprints are flattened from pool.items[] and use web_blueprint_link
"""

from src.starcitizenwiki_api.missions import BlueprintStub, Mission

# ── helpers ───────────────────────────────────────────────────────────────────

_STANDINGS = [
    {"name": "FactionRep_Neutral_Rank0", "display_name": "Neutral", "min_reputation": 0},
    {"name": "FactionRep_JrContractor_Rank1", "display_name": "Jr. Contractor", "min_reputation": 1000},
    {"name": "FactionRep_Contractor_Rank2", "display_name": "Contractor", "min_reputation": 2200},
]

_FACTION = {
    "name": "Vaughn",
    "uuid": "95761a82-18f9-4e25-ba33-d4c47c689324",
    "reputation_ladder": {"standings": _STANDINGS},
}

_BLUEPRINT_POOL = {
    "drop_chance": 1,
    "pool_uuid": "abc",
    "items": [
        {
            "name": "Badami Helmet",
            "uuid": "305c8b36-61a3-4065-b514-199719de9ac0",
            "web_blueprint_link": "https://api.star-citizen.wiki/blueprints/badami-helmet",
            "blueprint_link": "https://api.star-citizen.wiki/api/blueprints/badami-helmet",
        },
        {
            "name": "Killshot Rifle",
            "uuid": "aabbccdd-0000-0000-0000-000000000001",
            "web_blueprint_link": "https://api.star-citizen.wiki/blueprints/killshot-rifle",
            "blueprint_link": "https://api.star-citizen.wiki/api/blueprints/killshot-rifle",
        },
    ],
}

_MINIMAL = {
    "uuid": "f5affede-fed9-4d8b-a1ad-80f29f4ff216",
    "title": "A Challenging Contract",
    "illegal": False,
}


def _mission(**overrides) -> Mission:
    return Mission.from_api({**_MINIMAL, **overrides})


# ── rank_label ────────────────────────────────────────────────────────────────


class TestRankLabel:
    def test_resolves_label_from_standings(self):
        m = _mission(rank_index=2, faction=_FACTION)
        assert m.rank_label == "Contractor"

    def test_resolves_first_standing(self):
        m = _mission(rank_index=0, faction=_FACTION)
        assert m.rank_label == "Neutral"

    def test_none_when_rank_index_missing(self):
        m = _mission(faction=_FACTION)
        assert m.rank_label is None

    def test_none_when_faction_missing(self):
        m = _mission(rank_index=1)
        assert m.rank_label is None

    def test_none_when_reputation_ladder_missing(self):
        m = _mission(rank_index=1, faction={"name": "Vaughn"})
        assert m.rank_label is None

    def test_none_when_rank_index_out_of_range(self):
        m = _mission(rank_index=99, faction=_FACTION)
        assert m.rank_label is None

    def test_rank_index_still_stored(self):
        m = _mission(rank_index=2, faction=_FACTION)
        assert m.rank_index == 2


# ── blueprint flattening ──────────────────────────────────────────────────────


class TestBlueprintParsing:
    def test_flattens_pool_items_into_stubs(self):
        m = _mission(blueprints=[_BLUEPRINT_POOL])
        assert len(m.blueprints) == 2

    def test_blueprint_name_from_item(self):
        m = _mission(blueprints=[_BLUEPRINT_POOL])
        assert m.blueprints[0].name == "Badami Helmet"
        assert m.blueprints[1].name == "Killshot Rifle"

    def test_blueprint_link_uses_web_blueprint_link(self):
        m = _mission(blueprints=[_BLUEPRINT_POOL])
        assert m.blueprints[0].link == "https://api.star-citizen.wiki/blueprints/badami-helmet"

    def test_blueprint_link_falls_back_to_blueprint_link(self):
        item = {**_BLUEPRINT_POOL["items"][0]}
        del item["web_blueprint_link"]
        pool = {**_BLUEPRINT_POOL, "items": [item]}
        m = _mission(blueprints=[pool])
        assert m.blueprints[0].link == "https://api.star-citizen.wiki/api/blueprints/badami-helmet"

    def test_empty_blueprints_when_no_pools(self):
        assert _mission().blueprints == []

    def test_multiple_pools_flattened(self):
        pool2 = {**_BLUEPRINT_POOL, "pool_uuid": "xyz", "items": [_BLUEPRINT_POOL["items"][0]]}
        m = _mission(blueprints=[_BLUEPRINT_POOL, pool2])
        assert len(m.blueprints) == 3

    def test_non_dict_pool_entries_skipped(self):
        m = _mission(blueprints=["bad", None, _BLUEPRINT_POOL])
        assert len(m.blueprints) == 2

    def test_non_dict_item_entries_skipped(self):
        pool = {**_BLUEPRINT_POOL, "items": ["bad", _BLUEPRINT_POOL["items"][0]]}
        m = _mission(blueprints=[pool])
        assert len(m.blueprints) == 1


# ── BlueprintStub.from_api ────────────────────────────────────────────────────


class TestBlueprintStubFromApi:
    def test_parses_name(self):
        stub = BlueprintStub.from_api({"name": "Badami Helmet", "uuid": "abc", "web_blueprint_link": "https://x"})
        assert stub.name == "Badami Helmet"

    def test_defaults_name_to_unknown_when_missing(self):
        assert BlueprintStub.from_api({}).name == "Unknown"

    def test_uses_web_blueprint_link(self):
        stub = BlueprintStub.from_api({"web_blueprint_link": "https://wiki/bp", "blueprint_link": "https://api/bp"})
        assert stub.link == "https://wiki/bp"

    def test_falls_back_to_blueprint_link(self):
        stub = BlueprintStub.from_api({"blueprint_link": "https://api/bp"})
        assert stub.link == "https://api/bp"

    def test_empty_link_when_no_link_fields(self):
        assert BlueprintStub.from_api({}).link == ""
