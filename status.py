from dataclasses import dataclass
from mavsdk.telemetry import LandedState

@dataclass
class Position:
    lat: float
    long: float
    alt: float

@dataclass
class Status:
    pos: Position
    prio: int
    payload: float
    capacity: float
    landed_state: LandedState