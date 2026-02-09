from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import LVector3f


@dataclass
class MotionIntent:
    """Input intent for one simulation tick."""

    wish_dir: LVector3f
    crouching: bool
    jump_requested: bool
    dash_requested: bool = False
