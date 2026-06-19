"""Unit tests for the Executive Hangar domain model and schedule helpers."""

from datetime import UTC, datetime, timedelta

from src.exec_hangars.constants import (
    ACTIVE_DURATION,
    ACTIVE_INTERVAL,
    CHARGING_DURATION,
    CHARGING_INTERVAL,
    CYCLE_DURATION,
    LIGHT_COUNT,
)
from src.exec_hangars.hangar import ExecutiveHangar
from src.exec_hangars.schedule import HangarSchedule
from src.exec_hangars.states import HangarPhase, LightState
from src.exec_hangars.status import format_relative_time


class TestExecutiveHangar:
    def test_fresh_hangar_is_charging(self):
        assert ExecutiveHangar().phase is HangarPhase.CHARGING

    def test_fresh_hangar_has_zero_green_lights(self):
        assert ExecutiveHangar().green_lights == 0

    def test_fresh_hangar_is_not_open(self):
        assert not ExecutiveHangar().is_open

    def test_at_charging_one_light(self):
        h = ExecutiveHangar.at_charging(lights_green=1)
        assert h.phase is HangarPhase.CHARGING
        assert h.green_lights == 1

    def test_at_charging_all_lights_enters_active(self):
        h = ExecutiveHangar.at_charging(lights_green=LIGHT_COUNT)
        assert h.phase is HangarPhase.ACTIVE

    def test_at_active_is_open(self):
        h = ExecutiveHangar.at_active()
        assert h.phase is HangarPhase.ACTIVE
        assert h.is_open

    def test_at_active_decreasing_green_lights(self):
        h = ExecutiveHangar.at_active(lights_expired=2)
        assert h.green_lights == LIGHT_COUNT - 2

    def test_at_reset_is_blinking_not_open(self):
        h = ExecutiveHangar.at_reset()
        assert h.phase is HangarPhase.RESET
        assert h.is_blinking
        assert not h.is_open

    def test_charging_lights_green_then_red(self):
        h = ExecutiveHangar.at_charging(lights_green=2)
        lights = h.lights
        assert lights[:2] == [LightState.GREEN, LightState.GREEN]
        assert all(state is LightState.RED for state in lights[2:])

    def test_active_lights_green_first_expired_last(self):
        h = ExecutiveHangar.at_active(lights_expired=1)
        assert h.lights[-1] is LightState.EXPIRED
        assert all(state is LightState.GREEN for state in h.lights[:-1])

    def test_reset_all_lights_orange(self):
        assert all(state is LightState.ORANGE for state in ExecutiveHangar.at_reset().lights)

    def test_time_until_open_from_fresh_charging(self):
        assert ExecutiveHangar.at_charging().time_until_open == CHARGING_DURATION

    def test_time_until_open_when_active_is_zero(self):
        assert ExecutiveHangar.at_active().time_until_open == timedelta(0)

    def test_time_until_close_when_active(self):
        assert ExecutiveHangar.at_active().time_until_close == ACTIVE_DURATION

    def test_time_until_close_when_charging_is_zero(self):
        assert ExecutiveHangar.at_charging().time_until_close == timedelta(0)

    def test_time_until_next_change_charging_is_one_interval(self):
        h = ExecutiveHangar.at_charging(lights_green=0)
        assert h.time_until_next_change == CHARGING_INTERVAL

    def test_time_until_next_change_active_is_one_interval(self):
        h = ExecutiveHangar.at_active(lights_expired=0)
        assert h.time_until_next_change == ACTIVE_INTERVAL

    def test_advance_moves_into_active(self):
        h = ExecutiveHangar()
        h.advance(CHARGING_DURATION.total_seconds())
        assert h.phase is HangarPhase.ACTIVE

    def test_full_cycle_wraps_to_start(self):
        h = ExecutiveHangar()
        h.advance(CYCLE_DURATION.total_seconds())
        assert h.phase is HangarPhase.CHARGING
        assert h.green_lights == 0

    def test_light_panel_length_always_light_count(self):
        for factory in (
            ExecutiveHangar.at_charging,
            ExecutiveHangar.at_active,
            ExecutiveHangar.at_reset,
        ):
            assert len(factory().lights) == LIGHT_COUNT


class TestHangarSchedule:
    _NOW = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    def test_snapshot_reflects_charging_phase(self):
        schedule = HangarSchedule.from_charging(lights_green=0, observed_at=self._NOW)
        assert schedule.snapshot(self._NOW).phase is HangarPhase.CHARGING

    def test_snapshot_reflects_active_phase(self):
        schedule = HangarSchedule.from_active(observed_at=self._NOW)
        assert schedule.snapshot(self._NOW).phase is HangarPhase.ACTIVE

    def test_next_open_from_fresh_charging(self):
        schedule = HangarSchedule.from_charging(lights_green=0, observed_at=self._NOW)
        assert schedule.next_open(self._NOW) == self._NOW + CHARGING_DURATION

    def test_next_close_from_fresh_active(self):
        schedule = HangarSchedule.from_active(lights_expired=0, observed_at=self._NOW)
        assert schedule.next_close(self._NOW) == self._NOW + ACTIVE_DURATION

    def test_snapshot_roundtrip_preserves_green_lights(self):
        original = ExecutiveHangar.at_active(lights_expired=2)
        schedule = HangarSchedule.from_snapshot(original, observed_at=self._NOW)
        recovered = schedule.snapshot(self._NOW)
        assert recovered.phase is HangarPhase.ACTIVE
        assert recovered.green_lights == original.green_lights


class TestFormatRelativeTime:
    _NOW = datetime(2025, 6, 15, 14, 0, 0, tzinfo=UTC)

    def _dt(self, **delta_kwargs) -> datetime:
        return self._NOW - timedelta(**delta_kwargs)

    def test_same_day_says_today(self):
        earlier = datetime(2025, 6, 15, 9, 30, 0, tzinfo=UTC)
        assert format_relative_time(earlier, self._NOW).startswith("Today at")

    def test_previous_day_says_yesterday(self):
        assert format_relative_time(self._dt(days=1), self._NOW).startswith("Yesterday at")

    def test_three_days_ago(self):
        assert format_relative_time(self._dt(days=3), self._NOW) == "3 days ago"

    def test_one_week_ago(self):
        assert format_relative_time(self._dt(days=8), self._NOW) == "1 week ago"

    def test_two_weeks_ago(self):
        assert format_relative_time(self._dt(days=15), self._NOW) == "2 weeks ago"

    def test_one_month_ago(self):
        assert format_relative_time(self._dt(days=35), self._NOW) == "1 month ago"

    def test_three_months_ago(self):
        assert format_relative_time(self._dt(days=90), self._NOW) == "3 months ago"

    def test_one_year_ago_singular(self):
        assert format_relative_time(self._dt(days=370), self._NOW) == "1 year ago"

    def test_two_years_ago_plural(self):
        assert format_relative_time(self._dt(days=740), self._NOW) == "2 years ago"
