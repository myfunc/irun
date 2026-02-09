from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.physics.motion.config import MotionConfig, derive_motion_config
from ivan.physics.tuning import PhysicsTuning


class MotionSolver:
    """Single authority for derived run/jump/slide/gravity calculations."""

    def __init__(self, *, config: MotionConfig) -> None:
        self._config = config

    @classmethod
    def from_tuning(cls, *, tuning: PhysicsTuning) -> "MotionSolver":
        return cls(config=derive_motion_config(tuning=tuning))

    @property
    def config(self) -> MotionConfig:
        return self._config

    def sync_from_tuning(self, *, tuning: PhysicsTuning) -> None:
        self._config = derive_motion_config(tuning=tuning)

    def jump_takeoff_speed(self) -> float:
        return float(self._config.derived.jump_takeoff_speed)

    def gravity(self) -> float:
        return float(self._config.derived.gravity)

    def input_buffer_time(self, *, horizontal_speed: float | None = None) -> float:
        return self.grace_time_for_speed(horizontal_speed=horizontal_speed)

    def coyote_time(self, *, horizontal_speed: float | None = None) -> float:
        return self.grace_time_for_speed(horizontal_speed=horizontal_speed)

    def grace_time_for_speed(self, *, horizontal_speed: float | None = None) -> float:
        """
        Distance-based leniency window used by jump-buffer/coyote/vault grace checks.

        Backward-safe behavior: window never drops below configured grace_period.
        """

        base_t = max(0.0, float(self._config.invariants.grace_period))
        if base_t <= 0.0:
            return 0.0
        grace_dist = max(0.0, float(self._config.invariants.grace_distance))
        vmax = max(0.01, float(self._config.invariants.vmax))
        speed = abs(float(horizontal_speed)) if horizontal_speed is not None else vmax
        # Avoid exploding time at near-zero speed while preserving distance-derived behavior.
        speed = max(0.35 * vmax, speed)
        dist_t = grace_dist / speed if speed > 1e-9 else base_t
        # Never less forgiving than old fixed-time behavior; cap max expansion for stability.
        return max(base_t, min(base_t * 2.20, float(dist_t)))

    def slide_stop_t90(self) -> float:
        return float(self._config.invariants.slide_stop_t90)

    def air_speed(self, *, speed_scale: float = 1.0) -> float:
        return max(0.0, float(self._config.derived.air_speed) * max(0.0, float(speed_scale)))

    def air_accel(self) -> float:
        return max(0.0, float(self._config.derived.air_accel))

    def ground_target_speed(self, *, speed_scale: float) -> float:
        return max(0.0, float(self._config.invariants.vmax) * max(0.0, float(speed_scale)))

    def apply_ground_run(self, *, vel: LVector3f, wish_dir: LVector3f, dt: float, speed_scale: float) -> None:
        """Derived exponential run response from Vmax + T90."""

        wish = self._horizontal_unit(wish_dir)
        if wish.lengthSquared() <= 1e-12:
            return

        target_speed = self.ground_target_speed(speed_scale=speed_scale)
        target = wish * target_speed
        current = LVector3f(vel.x, vel.y, 0.0)

        k = max(0.0, float(self._config.derived.run_exp_k))
        alpha = 1.0 - math.exp(-k * max(0.0, float(dt)))
        alpha = max(0.0, min(1.0, alpha))
        current += (target - current) * alpha

        vel.x = current.x
        vel.y = current.y

    def apply_ground_coast_damping(self, *, vel: LVector3f, dt: float) -> None:
        """Exponential ground slowdown derived from stop-time invariant."""

        k = max(0.0, float(self._config.derived.ground_damp_k))
        if k <= 1e-12:
            return
        damp = math.exp(-k * max(0.0, float(dt)))
        vel.x *= damp
        vel.y *= damp

    @staticmethod
    def apply_air_accel(
        *,
        vel: LVector3f,
        wish_dir: LVector3f,
        dt: float,
        wish_speed: float,
        accel: float,
    ) -> None:
        """Quake-style air acceleration under one solver API."""

        if wish_dir.lengthSquared() <= 0.0:
            return

        current_speed = float(vel.dot(wish_dir))
        add_speed = float(wish_speed) - current_speed
        if add_speed > 0.0:
            accel_speed = float(accel) * float(dt) * float(wish_speed)
            accel_speed = min(accel_speed, add_speed)
            vel += wish_dir * accel_speed

    def apply_gravity(self, *, vel: LVector3f, dt: float, gravity_scale: float = 1.0) -> None:
        vel.z -= self.gravity() * max(0.0, float(gravity_scale)) * max(0.0, float(dt))

    def apply_slide_ground_damping(self, *, speed: float, dt: float) -> float:
        k = max(0.0, float(self._config.derived.slide_damp_k))
        if k <= 1e-12:
            return max(0.0, float(speed))
        return max(0.0, float(speed) * math.exp(-k * max(0.0, float(dt))))

    def apply_wallrun_sink(self, *, vel: LVector3f, dt: float) -> None:
        # Preserve upward launch carry. Only control descending/neutral vertical on active wallrun.
        if float(vel.z) > 0.0:
            return
        k = max(0.0, float(self._config.derived.wallrun_sink_k))
        if k <= 1e-12:
            return
        alpha = 1.0 - math.exp(-k * max(0.0, float(dt)))
        alpha = max(0.0, min(1.0, alpha))
        sink = float(self._config.derived.wallrun_sink_speed)
        vel.z += (sink - float(vel.z)) * alpha

    @staticmethod
    def _horizontal_unit(vec: LVector3f) -> LVector3f:
        out = LVector3f(vec.x, vec.y, 0.0)
        if out.lengthSquared() > 1e-12:
            out.normalize()
        return out
