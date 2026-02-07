from __future__ import annotations

from dataclasses import dataclass

from panda3d.core import LVector3f


@dataclass(frozen=True)
class AABB:
    minimum: LVector3f
    maximum: LVector3f

