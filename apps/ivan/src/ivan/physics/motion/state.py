from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from panda3d.core import LVector3f


class MotionMode(str, Enum):
    GROUND = "ground"
    AIR = "air"
    DASH = "dash"
    ATTACK = "attack"
    HITSTOP = "hitstop"
    KNOCKBACK = "knockback"


@dataclass
class MotionState:
    vel: LVector3f
    grounded: bool
    mode: MotionMode
    coyote_time_left: float = 0.0
    dash_time_left: float = 0.0
    hitstop: bool = False
    knockback: bool = False
