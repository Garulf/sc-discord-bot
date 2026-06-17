from enum import Enum, auto


class HangarPhase(Enum):
    CHARGING = auto()
    ACTIVE = auto()
    RESET = auto()


class LightState(Enum):
    RED = auto()
    GREEN = auto()
    EXPIRED = auto()
    ORANGE = auto()
