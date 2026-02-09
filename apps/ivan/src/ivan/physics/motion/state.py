from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from panda3d.core import LVector3f


class MotionMode(str, Enum):
    GROUND = "ground"
    AIR = "air"
    SLIDE = "slide"
    ATTACK = "attack"
    HITSTOP = "hitstop"
    KNOCKBACK = "knockback"


class MotionWriteSource(str, Enum):
    SOLVER = "solver"
    IMPULSE = "impulse"
    COLLISION = "collision"
    CONSTRAINT = "constraint"
    EXTERNAL = "external"


@dataclass
class MotionState:
    vel: LVector3f
    grounded: bool
    mode: MotionMode
    coyote_time_left: float = 0.0
    slide_active: bool = False
    hitstop: bool = False
    knockback: bool = False
