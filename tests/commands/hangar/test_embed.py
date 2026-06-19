"""Unit tests for src.commands.hangar.embed — build_embed."""

from datetime import UTC, datetime

from src.commands.hangar.embed import build_embed
from src.exec_hangars.schedule import HangarSchedule
from src.exec_hangars.states import HangarPhase
from src.exec_hangars.status import PHASE_COLOR

_NOW = datetime(2025, 3, 15, 12, 0, 0, tzinfo=UTC)
_SET_AT = datetime(2025, 3, 15, 11, 30, 0, tzinfo=UTC)


class TestBuildEmbed:
    def test_title_comes_from_build_status(self):
        embed = build_embed(HangarSchedule.from_charging(observed_at=_NOW), now=_NOW)
        assert embed.title == "Executive Hangar"

    def test_color_matches_phase(self):
        embed = build_embed(HangarSchedule.from_active(observed_at=_NOW), now=_NOW)
        assert embed.color.value == PHASE_COLOR[HangarPhase.ACTIVE]

    def test_description_contains_phase_info(self):
        embed = build_embed(HangarSchedule.from_charging(observed_at=_NOW), now=_NOW)
        assert embed.description is not None
        assert len(embed.description) > 0

    def test_footer_includes_updated(self):
        embed = build_embed(HangarSchedule.from_charging(observed_at=_NOW), now=_NOW)
        assert "Updated" in embed.footer.text

    def test_footer_includes_synced_when_set_at_provided(self):
        embed = build_embed(HangarSchedule.from_charging(observed_at=_NOW), now=_NOW, set_at=_SET_AT)
        assert "Synced" in embed.footer.text

    def test_footer_no_synced_when_set_at_none(self):
        embed = build_embed(HangarSchedule.from_charging(observed_at=_NOW), now=_NOW, set_at=None)
        assert "Synced" not in embed.footer.text

    def test_charging_phase_embed_mentions_opens(self):
        embed = build_embed(HangarSchedule.from_charging(observed_at=_NOW), now=_NOW)
        assert "Opens" in embed.description

    def test_active_phase_embed_mentions_closes(self):
        embed = build_embed(HangarSchedule.from_active(observed_at=_NOW), now=_NOW)
        assert "Closes" in embed.description

    def test_reset_phase_embed_has_correct_color(self):
        embed = build_embed(HangarSchedule.from_reset(observed_at=_NOW), now=_NOW)
        assert embed.color.value == PHASE_COLOR[HangarPhase.RESET]
