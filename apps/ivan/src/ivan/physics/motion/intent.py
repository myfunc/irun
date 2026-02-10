from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import LVector3f


@dataclass
class MotionIntent:
    """Input intent for one simulation tick."""

    wish_dir: LVector3f
    jump_requested: bool
    # Hold semantics: True while slide key is held down.
    slide_requested: bool = False
