"""Unit tests for src.exec_hangars.status — discord_timestamp, render_lights, build_status."""

from datetime import UTC, datetime

from src.exec_hangars.constants import LIGHT_COUNT
from src.exec_hangars.hangar import ExecutiveHangar
from src.exec_hangars.schedule import HangarSchedule
from src.exec_hangars.states import HangarPhase
from src.exec_hangars.status import PHASE_COLOR, build_status, discord_timestamp, render_lights


class TestDiscordTimestamp:
    _MOMENT = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)

    def test_default_style_is_relative(self):
        result = discord_timestamp(self._MOMENT)
        assert result.endswith(":R>")

    def test_contains_unix_timestamp(self):
        result = discord_timestamp(self._MOMENT)
        assert str(int(self._MOMENT.timestamp())) in result

    def test_custom_style_applied(self):
        result = discord_timestamp(self._MOMENT, style="F")
        assert result.endswith(":F>")

    def test_format_is_discord_timestamp_tag(self):
        result = discord_timestamp(self._MOMENT)
        assert result.startswith("<t:") and result.endswith(">")

    def test_exact_format(self):
        unix = int(self._MOMENT.timestamp())
        assert discord_timestamp(self._MOMENT) == f"<t:{unix}:R>"


class TestRenderLights:
    def test_charging_two_green_shows_correct_emojis(self):
        h = ExecutiveHangar.at_charging(lights_green=2)
        result = render_lights(h)
        assert result.count("🟩") == 2
        assert result.count("🟥") == LIGHT_COUNT - 2

    def test_active_no_expired_shows_all_green(self):
        h = ExecutiveHangar.at_active(lights_expired=0)
        result = render_lights(h)
        assert result.count("🟩") == LIGHT_COUNT
        assert "🟥" not in result

    def test_active_one_expired_shows_correct_split(self):
        h = ExecutiveHangar.at_active(lights_expired=1)
        result = render_lights(h)
        assert result.count("🟩") == LIGHT_COUNT - 1
        assert result.count("⬛") == 1

    def test_reset_shows_all_orange(self):
        h = ExecutiveHangar.at_reset()
        result = render_lights(h)
        assert result.count("🟧") == LIGHT_COUNT
        assert "🟩" not in result

    def test_lights_are_space_separated(self):
        h = ExecutiveHangar.at_active()
        parts = render_lights(h).split(" ")
        assert len(parts) == LIGHT_COUNT


class TestBuildStatus:
    _NOW = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    def test_title_is_always_executive_hangar(self):
        status = build_status(HangarSchedule.from_charging(observed_at=self._NOW), self._NOW)
        assert status["title"] == "Executive Hangar"

    def test_charging_phase_color(self):
        status = build_status(HangarSchedule.from_charging(observed_at=self._NOW), self._NOW)
        assert status["color"] == PHASE_COLOR[HangarPhase.CHARGING]

    def test_active_phase_color(self):
        status = build_status(HangarSchedule.from_active(observed_at=self._NOW), self._NOW)
        assert status["color"] == PHASE_COLOR[HangarPhase.ACTIVE]

    def test_reset_phase_color(self):
        status = build_status(HangarSchedule.from_reset(observed_at=self._NOW), self._NOW)
        assert status["color"] == PHASE_COLOR[HangarPhase.RESET]

    def test_charging_description_shows_closed_state(self):
        status = build_status(HangarSchedule.from_charging(observed_at=self._NOW), self._NOW)
        assert "Closed" in status["description"]

    def test_active_description_shows_open_state(self):
        status = build_status(HangarSchedule.from_active(observed_at=self._NOW), self._NOW)
        assert "Open" in status["description"]

    def test_active_description_shows_closes_timestamp(self):
        status = build_status(HangarSchedule.from_active(observed_at=self._NOW), self._NOW)
        assert "Closes" in status["description"]

    def test_charging_description_shows_opens_timestamp(self):
        status = build_status(HangarSchedule.from_charging(observed_at=self._NOW), self._NOW)
        assert "Opens" in status["description"]

    def test_description_shows_next_light_change(self):
        status = build_status(HangarSchedule.from_charging(observed_at=self._NOW), self._NOW)
        assert "Next light change" in status["description"]

    def test_phase_key_matches_hangar_phase(self):
        for factory, expected_phase in (
            (HangarSchedule.from_charging, HangarPhase.CHARGING),
            (HangarSchedule.from_active, HangarPhase.ACTIVE),
            (HangarSchedule.from_reset, HangarPhase.RESET),
        ):
            status = build_status(factory(observed_at=self._NOW), self._NOW)
            assert status["phase"] is expected_phase

    def test_description_includes_light_count_fraction(self):
        status = build_status(HangarSchedule.from_charging(lights_green=2, observed_at=self._NOW), self._NOW)
        assert f"2/{LIGHT_COUNT}" in status["description"]
