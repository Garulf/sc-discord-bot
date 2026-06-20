"""Tests for build_blueprint_embed — covers the two display bugs fixed:

1. Missions with <= UNINITIALIZED => titles are filtered out.
2. The "Unlocked By" field truncates at a complete line boundary (never
   mid-markdown-link) and appends "… and N more" instead of cutting a URL.
"""

from __future__ import annotations

from src.commands.find.blueprint import build_blueprint_embed
from src.starcitizenwiki_api.blueprints import Blueprint, UnlockingMission, UnlockingMissionGroup


def _blueprint(**overrides) -> Blueprint:
    defaults = dict(
        uuid="b627e348-29b5-44c8-a836-258df60bcd08",
        name="FS-9 LMG",
        web_url="https://example.com/bp",
        key=None,
        craft_time_seconds=None,
        craft_time_label=None,
        ingredient_count=None,
        unlocking_missions_count=None,
        is_available_by_default=None,
        output_class=None,
        output_type=None,
        output_type_label=None,
        ingredients=[],
        unlocking_missions_grouped=[],
    )
    return Blueprint(**{**defaults, **overrides})


def _group(missions: list[UnlockingMission], label: str = "Guaranteed", chance: float = 1.0) -> UnlockingMissionGroup:
    return UnlockingMissionGroup(label=label, chance=chance, missions=missions)


def _mission(title: str, web_url: str | None = None, count: int = 1) -> UnlockingMission:
    return UnlockingMission(title=title, reward_scope=None, count=count, web_url=web_url)


def _field(embed, name: str) -> str | None:
    for f in embed.fields:
        if f.name == name:
            return f.value
    return None


# ── UNINITIALIZED sentinel filtering ─────────────────────────────────────────


class TestUninitializedFiltering:
    def test_uninitialized_title_omitted(self):
        group = _group([
            _mission("<= UNINITIALIZED =>", "https://example.com/m1"),
            _mission("Clear Outlaw Data Center", "https://example.com/m2"),
        ])
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        value = _field(embed, "Unlocked By")
        assert "<= UNINITIALIZED =>" not in value

    def test_valid_missions_still_shown(self):
        group = _group([
            _mission("<= UNINITIALIZED =>"),
            _mission("Clear Outlaw Data Center", "https://example.com/m"),
        ])
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        value = _field(embed, "Unlocked By")
        assert "Clear Outlaw Data Center" in value

    def test_all_uninitialized_produces_no_field(self):
        group = _group([_mission("<= UNINITIALIZED =>")])
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        assert _field(embed, "Unlocked By") is None

    def test_other_angle_bracket_patterns_also_filtered(self):
        group = _group([_mission("<= SOME_OTHER_SENTINEL =>"), _mission("Real Mission")])
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        value = _field(embed, "Unlocked By")
        assert "<= SOME_OTHER_SENTINEL =>" not in value
        assert "Real Mission" in value


# ── truncation ────────────────────────────────────────────────────────────────


class TestUnlockingMissionsTruncation:
    def test_short_list_shown_in_full(self):
        group = _group([_mission(f"Mission {i}", f"https://example.com/{i}") for i in range(5)])
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        value = _field(embed, "Unlocked By")
        assert "Mission 4" in value

    def test_truncation_appends_more_count(self):
        long_url = "https://example.com/" + "x" * 80
        missions = [_mission(f"Mission {i:02d}", long_url) for i in range(20)]
        group = _group(missions)
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        value = _field(embed, "Unlocked By")
        assert "… and" in value and "more" in value

    def test_truncation_never_cuts_mid_link(self):
        long_url = "https://example.com/" + "x" * 80
        missions = [_mission(f"Mission {i:02d}", long_url) for i in range(20)]
        group = _group(missions)
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        value = _field(embed, "Unlocked By")
        # Every markdown link must be complete: no bare '(' or truncated URLs
        assert "](h" not in value or value.count("](") == value.count(")\n") + value.endswith(")")

    def test_field_value_within_discord_limit(self):
        long_url = "https://example.com/" + "x" * 80
        missions = [_mission(f"Mission {i:02d}", long_url) for i in range(30)]
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[_group(missions)]))
        value = _field(embed, "Unlocked By")
        assert len(value) <= 1024

    def test_count_shown_after_title(self):
        group = _group([_mission("Destroy Data", "https://example.com/m", count=3)])
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        assert "×3" in _field(embed, "Unlocked By")

    def test_no_url_renders_plain_title(self):
        group = _group([_mission("Some Mission", web_url=None)])
        embed = build_blueprint_embed(_blueprint(unlocking_missions_grouped=[group]))
        value = _field(embed, "Unlocked By")
        assert "Some Mission" in value
        assert "](None)" not in value
