from datetime import datetime, timezone
from typing import Optional

from src.exec_hangars.hangar import ExecutiveHangar


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HangarSchedule:
    def __init__(self, cycle_start: datetime) -> None:
        self._cycle_start = cycle_start

    @classmethod
    def from_snapshot(cls, hangar: ExecutiveHangar, observed_at: Optional[datetime] = None) -> "HangarSchedule":
        moment = observed_at if observed_at is not None else _utcnow()
        return cls(moment - hangar.elapsed)

    @classmethod
    def from_charging(cls, lights_green: int = 0, observed_at: Optional[datetime] = None) -> "HangarSchedule":
        return cls.from_snapshot(ExecutiveHangar.at_charging(lights_green), observed_at)

    @classmethod
    def from_active(cls, lights_expired: int = 0, observed_at: Optional[datetime] = None) -> "HangarSchedule":
        return cls.from_snapshot(ExecutiveHangar.at_active(lights_expired), observed_at)

    @classmethod
    def from_reset(cls, elapsed_seconds: float = 0, observed_at: Optional[datetime] = None) -> "HangarSchedule":
        return cls.from_snapshot(ExecutiveHangar.at_reset(elapsed_seconds), observed_at)

    @property
    def cycle_start(self) -> datetime:
        return self._cycle_start

    def snapshot(self, now: Optional[datetime] = None) -> ExecutiveHangar:
        moment = self._resolve(now)
        return ExecutiveHangar(elapsed_seconds=(moment - self._cycle_start).total_seconds())

    def next_open(self, now: Optional[datetime] = None) -> datetime:
        moment = self._resolve(now)
        return moment + self.snapshot(moment).time_until_open

    def next_close(self, now: Optional[datetime] = None) -> datetime:
        moment = self._resolve(now)
        return moment + self.snapshot(moment).time_until_close

    def next_change(self, now: Optional[datetime] = None) -> datetime:
        moment = self._resolve(now)
        return moment + self.snapshot(moment).time_until_next_change

    @staticmethod
    def _resolve(now: Optional[datetime]) -> datetime:
        return now if now is not None else _utcnow()

    def __repr__(self) -> str:
        return f"HangarSchedule(cycle_start={self._cycle_start.isoformat()})"
