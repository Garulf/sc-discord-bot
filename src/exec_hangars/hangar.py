from dataclasses import dataclass
from datetime import timedelta

from src.exec_hangars.constants import (
    ACTIVE_DURATION,
    ACTIVE_INTERVAL,
    CHARGING_DURATION,
    CHARGING_INTERVAL,
    CYCLE_DURATION,
    LIGHT_COUNT,
    RESET_DURATION,
)
from src.exec_hangars.states import HangarPhase, LightState


@dataclass(frozen=True)
class PhaseSlice:
    phase: HangarPhase
    offset: timedelta
    duration: timedelta

    @property
    def remaining(self) -> timedelta:
        return self.duration - self.offset


_PHASE_STARTS = {
    HangarPhase.CHARGING: timedelta(0),
    HangarPhase.ACTIVE: CHARGING_DURATION,
    HangarPhase.RESET: CHARGING_DURATION + ACTIVE_DURATION,
}


class ExecutiveHangar:
    def __init__(self, phase: HangarPhase = HangarPhase.CHARGING, elapsed_seconds: float = 0) -> None:
        position = _PHASE_STARTS[phase] + timedelta(seconds=elapsed_seconds)
        self._elapsed = position % CYCLE_DURATION

    @classmethod
    def at_charging(cls, lights_green: int = 0) -> "ExecutiveHangar":
        return cls(HangarPhase.CHARGING, (lights_green * CHARGING_INTERVAL).total_seconds())

    @classmethod
    def at_active(cls, lights_expired: int = 0) -> "ExecutiveHangar":
        return cls(HangarPhase.ACTIVE, (lights_expired * ACTIVE_INTERVAL).total_seconds())

    @classmethod
    def at_reset(cls, elapsed_seconds: float = 0) -> "ExecutiveHangar":
        return cls(HangarPhase.RESET, elapsed_seconds)

    @property
    def elapsed(self) -> timedelta:
        return self._elapsed

    @property
    def phase(self) -> HangarPhase:
        return self._slice().phase

    @property
    def green_lights(self) -> int:
        slice_ = self._slice()
        if slice_.phase is HangarPhase.CHARGING:
            return slice_.offset // CHARGING_INTERVAL
        if slice_.phase is HangarPhase.ACTIVE:
            return LIGHT_COUNT - slice_.offset // ACTIVE_INTERVAL
        return 0

    @property
    def lights(self) -> list[LightState]:
        slice_ = self._slice()
        if slice_.phase is HangarPhase.RESET:
            return [LightState.ORANGE] * LIGHT_COUNT
        return self._light_panel(slice_.phase)

    @property
    def is_open(self) -> bool:
        return self.phase is HangarPhase.ACTIVE

    @property
    def is_blinking(self) -> bool:
        return self.phase is HangarPhase.RESET

    @property
    def time_until_next_change(self) -> timedelta:
        slice_ = self._slice()
        if slice_.phase is HangarPhase.CHARGING:
            return CHARGING_INTERVAL - slice_.offset % CHARGING_INTERVAL
        if slice_.phase is HangarPhase.ACTIVE:
            return ACTIVE_INTERVAL - slice_.offset % ACTIVE_INTERVAL
        return slice_.remaining

    @property
    def time_until_open(self) -> timedelta:
        slice_ = self._slice()
        if slice_.phase is HangarPhase.ACTIVE:
            return timedelta(0)
        if slice_.phase is HangarPhase.CHARGING:
            return slice_.remaining
        return slice_.remaining + CHARGING_DURATION

    @property
    def time_until_close(self) -> timedelta:
        slice_ = self._slice()
        if slice_.phase is HangarPhase.ACTIVE:
            return slice_.remaining
        return timedelta(0)

    def advance(self, seconds: float) -> None:
        self._elapsed = (self._elapsed + timedelta(seconds=seconds)) % CYCLE_DURATION

    def _light_panel(self, phase: HangarPhase) -> list[LightState]:
        lit = self.green_lights
        dormant = LightState.RED if phase is HangarPhase.CHARGING else LightState.EXPIRED
        return [LightState.GREEN if index < lit else dormant for index in range(LIGHT_COUNT)]

    def _slice(self) -> PhaseSlice:
        offset = self._elapsed
        if offset < CHARGING_DURATION:
            return PhaseSlice(HangarPhase.CHARGING, offset, CHARGING_DURATION)
        offset -= CHARGING_DURATION
        if offset < ACTIVE_DURATION:
            return PhaseSlice(HangarPhase.ACTIVE, offset, ACTIVE_DURATION)
        offset -= ACTIVE_DURATION
        return PhaseSlice(HangarPhase.RESET, offset, RESET_DURATION)

    def __repr__(self) -> str:
        return (
            f"ExecutiveHangar(phase={self.phase.name}, "
            f"green_lights={self.green_lights}, "
            f"next_change={self.time_until_next_change})"
        )
