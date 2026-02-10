from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.physics.motion.state import MotionWriteSource


class PlayerControllerMomentumMixin:
    @staticmethod
    def _horizontal_speed_of(vel: LVector3f) -> float:
        return math.sqrt(float(vel.x) * float(vel.x) + float(vel.y) * float(vel.y))

    @staticmethod
    def _total_speed_of(vel: LVector3f) -> float:
        return math.sqrt(float(vel.x) * float(vel.x) + float(vel.y) * float(vel.y) + float(vel.z) * float(vel.z))

    def _preserve_horizontal_speed_floor(self, *, floor: float, ref_vel: LVector3f, reason: str) -> None:
        target = max(0.0, float(floor))
        if target <= 1e-4:
            return
        current = self._horizontal_speed_of(self.vel)
        # Keep a tiny tolerance to avoid oscillation/noise.
        if current >= target * 0.995:
            return
        deficit = target - current
        if deficit <= 1e-6:
            return

        direction = LVector3f(float(self.vel.x), float(self.vel.y), 0.0)
        if direction.lengthSquared() <= 1e-12:
            direction = LVector3f(float(ref_vel.x), float(ref_vel.y), 0.0)
        if direction.lengthSquared() <= 1e-12:
            return
        direction.normalize()
        self._set_horizontal_velocity(
            x=float(self.vel.x) + float(direction.x) * deficit,
            y=float(self.vel.y) + float(direction.y) * deficit,
            source=MotionWriteSource.SOLVER,
            reason=str(reason),
        )

    def _preserve_total_speed_floor(self, *, floor: float, ref_vel: LVector3f, reason: str) -> None:
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
            reason=str(reason),
        )

    def _should_preserve_total_speed(self) -> bool:
        if self.is_grapple_attached():
            return True
        if self._wallrun_reacquire_block_timer > 0.0:
            return True
        return self.is_wallrunning() and float(self.vel.z) <= 0.0

    def _apply_momentum_policy(
        self,
        *,
        pre_vel: LVector3f,
        started_grounded: bool,
        jumped_this_tick: bool,
    ) -> None:
        # Priority override lanes can intentionally reshape speed.
        if self._hitstop_active or self._knockback_active:
            return
        # Only regular grounded run/coast is allowed to decelerate by policy.
        if started_grounded and not self.is_sliding() and not jumped_this_tick:
            return

        pre_h = self._horizontal_speed_of(pre_vel)
        self._preserve_horizontal_speed_floor(
            floor=pre_h,
            ref_vel=pre_vel,
            reason="momentum_policy.horizontal_floor",
        )
        if self._should_preserve_total_speed():
            pre_total = self._total_speed_of(pre_vel)
            self._preserve_total_speed_floor(
                floor=pre_total,
                ref_vel=pre_vel,
                reason="momentum_policy.total_floor",
            )
