from __future__ import annotations

from src.starcitizenwiki_api.missions import HaulingOrder, Mission, RewardItem


class TestRewardItem:
    def test_from_api_full(self):
        data = {
            "name": "Anvil F8C Lightning Wikelo War Special",
            "uuid": "71f76583-1061-4215-9d05-839a4fb6cabc",
            "amount": 1,
            "web_url": "https://api.star-citizen.wiki/items/anvil-f8c",
            "link": "https://api.star-citizen.wiki/api/items/71f76583-1061-4215-9d05-839a4fb6cabc",
        }
        item = RewardItem.from_api(data)
        assert item.name == "Anvil F8C Lightning Wikelo War Special"
        assert item.uuid == "71f76583-1061-4215-9d05-839a4fb6cabc"
        assert item.amount == 1
        assert item.web_url == "https://api.star-citizen.wiki/items/anvil-f8c"
        assert item.link == "https://api.star-citizen.wiki/api/items/71f76583-1061-4215-9d05-839a4fb6cabc"

    def test_from_api_missing_optional_fields(self):
        item = RewardItem.from_api({"name": "Helmet", "uuid": "abc", "amount": 2})
        assert item.web_url is None
        assert item.link is None

    def test_from_api_missing_name_defaults_to_unknown(self):
        item = RewardItem.from_api({"uuid": "abc", "amount": 1})
        assert item.name == "Unknown"

    def test_from_api_missing_amount_defaults_to_one(self):
        item = RewardItem.from_api({"name": "Thing", "uuid": "abc"})
        assert item.amount == 1


class TestHaulingOrder:
    def test_from_api_full(self):
        data = {
            "name": "Wikelo Favor",
            "uuid": "3b1cf59f-1e6b-4a91-9edb-f8c5ddf791ae",
            "min_amount": None,
            "max_amount": 40,
            "web_url": "https://api.star-citizen.wiki/items/3b1cf59f",
        }
        order = HaulingOrder.from_api(data)
        assert order.name == "Wikelo Favor"
        assert order.min_amount is None
        assert order.max_amount == 40
        assert order.web_url == "https://api.star-citizen.wiki/items/3b1cf59f"

    def test_from_api_equal_amounts(self):
        order = HaulingOrder.from_api({"name": "Carinite (Pure)", "uuid": "x", "min_amount": 4, "max_amount": 4})
        assert order.min_amount == 4
        assert order.max_amount == 4

    def test_from_api_missing_amounts(self):
        order = HaulingOrder.from_api({"name": "Ore", "uuid": "y"})
        assert order.min_amount is None
        assert order.max_amount is None


class TestMissionRewardFields:
    def test_reward_items_parsed_from_api(self):
        data = _minimal_mission_data()
        data["reward_items"] = [
            {"name": "Anvil F8C Lightning Wikelo War Special", "uuid": "abc", "amount": 1}
        ]
        mission = Mission.from_api(data)
        assert len(mission.reward_items) == 1
        assert mission.reward_items[0].name == "Anvil F8C Lightning Wikelo War Special"

    def test_hauling_orders_parsed_from_api(self):
        data = _minimal_mission_data()
        data["hauling_orders"] = [
            {"name": "Wikelo Favor", "uuid": "x", "min_amount": None, "max_amount": 40},
            {"name": "Carinite (Pure)", "uuid": "y", "min_amount": 4, "max_amount": 4},
        ]
        mission = Mission.from_api(data)
        assert len(mission.hauling_orders) == 2
        assert mission.hauling_orders[0].name == "Wikelo Favor"
        assert mission.hauling_orders[1].min_amount == 4

    def test_reward_items_empty_when_absent(self):
        mission = Mission.from_api(_minimal_mission_data())
        assert mission.reward_items == []

    def test_hauling_orders_empty_when_absent(self):
        mission = Mission.from_api(_minimal_mission_data())
        assert mission.hauling_orders == []


def _minimal_mission_data() -> dict:
    return {
        "uuid": "test-uuid",
        "title": "F8 War Mod",
        "description": None,
        "mission_type": "Wikelo - Vehicles",
        "mission_giver": "Wikelo",
        "faction": {"name": "Wikelo Emporium", "uuid": "faction-uuid"},
        "rank_index": None,
        "illegal": False,
        "legality_label": "Legal",
        "shareable": False,
        "once_only": False,
        "has_combat": False,
        "enemy_count_min": None,
        "enemy_count_max": None,
        "reward_min": None,
        "reward_max": None,
        "reward_currency": None,
        "reward_scope": "Other",
        "time_to_complete_minutes": None,
        "star_systems": ["Stanton"],
        "has_blueprints": False,
        "has_chain": False,
        "has_prerequisites": False,
        "max_players_per_instance": 1,
        "cooldown_label": None,
        "reputation_amount": 250,
        "web_url": "https://api.star-citizen.wiki/missions/f8-war-mod",
    }
