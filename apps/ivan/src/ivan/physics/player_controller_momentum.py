from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.physics.motion.state import MotionWriteSource


class PlayerControllerMomentumMixin:
    @staticmethod
    def _total_speed_of(vel: LVector3f) -> float:
        return math.sqrt(float(vel.x) * float(vel.x) + float(vel.y) * float(vel.y) + float(vel.z) * float(vel.z))

    def _preserve_total_speed_floor(self, *, floor: float, ref_vel: LVector3f) -> None:
        target = max(0.0, float(floor))
        if target <= 1e-4:
            return
        current = self._total_speed_of(self.vel)
        if current >= target * 0.995:
            return
        deficit = target - current
        if deficit <= 1e-6:
            return

        direction = LVector3f(self.vel)
        if direction.lengthSquared() <= 1e-12:
            direction = LVector3f(ref_vel)
        if direction.lengthSquared() <= 1e-12:
            return
        direction.normalize()
        self._add_velocity(
            direction * deficit,
            source=MotionWriteSource.SOLVER,
            reason="walljump.preserve_total",
        )
