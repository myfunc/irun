from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.physics.motion.state import MotionWriteSource


class PlayerControllerKinematicsMixin:
    def _consume_jump_request(self) -> bool:
        if self._jump_pressed:
            self._jump_pressed = False
            return True
        if not bool(self.tuning.coyote_buffer_enabled):
            return False
        return self._jump_buffer_timer > 0.0

    def _start_slide(self, *, yaw_deg: float) -> None:
        if not self.grounded:
            return
        if self._slide_active:
            return

        hvel = LVector3f(self.vel.x, self.vel.y, 0.0)
        slide_dir = self._horizontal_unit(hvel)
        if slide_dir.lengthSquared() <= 1e-12:
            h_rad = math.radians(float(yaw_deg))
            slide_dir = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if slide_dir.lengthSquared() <= 1e-12:
            return
        slide_dir.normalize()

        self._slide_dir = LVector3f(slide_dir)
        self._slide_active = True
        self._slide_ground_grace_timer = max(float(self._slide_ground_grace_timer), 0.08)
        cur_hspeed = math.sqrt(float(self.vel.x) * float(self.vel.x) + float(self.vel.y) * float(self.vel.y))
        self._set_horizontal_velocity(
            x=float(self._slide_dir.x) * cur_hspeed,
            y=float(self._slide_dir.y) * cur_hspeed,
            source=MotionWriteSource.IMPULSE,
            reason="slide.start",
        )

    def _step_slide_mode(self, *, dt: float, yaw_deg: float) -> None:
        # Slide owns horizontal velocity while active.
        if self._slide_dir.lengthSquared() <= 1e-12:
            self._slide_dir = self._horizontal_unit(LVector3f(self.vel.x, self.vel.y, 0.0))
        if self._slide_dir.lengthSquared() <= 1e-12:
            return

        self._slide_dir.normalize()

        # Slide steering is camera-only: keyboard strafing is ignored while slide owns velocity.
        h_rad = math.radians(float(yaw_deg))
        cam_dir = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if cam_dir.lengthSquared() > 1e-12:
            cam_dir.normalize()
            blend = max(0.0, min(1.0, float(dt) * 14.0))
            out = self._slide_dir * (1.0 - blend) + cam_dir * blend
            if out.lengthSquared() > 1e-12:
                out.normalize()
                self._slide_dir = out

        hspeed = math.sqrt(float(self.vel.x) * float(self.vel.x) + float(self.vel.y) * float(self.vel.y))
        hspeed = self._motion_solver.apply_slide_ground_damping(speed=hspeed, dt=dt)
        hspeed = max(0.0, hspeed + self._slide_slope_speed_delta(dt=dt))
        self._set_horizontal_velocity(
            x=float(self._slide_dir.x) * hspeed,
            y=float(self._slide_dir.y) * hspeed,
            source=MotionWriteSource.SOLVER,
            reason="slide.solve",
        )
        self._motion_solver.apply_gravity(vel=self.vel, dt=dt, gravity_scale=1.0)

        if self._consume_jump_request() and self._can_coyote_jump():
            if bool(self.tuning.vault_enabled) and self._try_vault(yaw_deg=yaw_deg):
                return
            self._apply_jump()

    def _slide_slope_speed_delta(self, *, dt: float) -> float:
        if not self.grounded:
            return 0.0
        n = LVector3f(self._ground_normal)
        if n.lengthSquared() <= 1e-12:
            return 0.0
        n.normalize()

        gravity_dir = LVector3f(0.0, 0.0, -1.0)
        slope_vec = LVector3f(gravity_dir - n * float(gravity_dir.dot(n)))
        slope_h = LVector3f(float(slope_vec.x), float(slope_vec.y), 0.0)
        slope_mag = float(slope_h.length())
        if slope_mag <= 1e-6:
            return 0.0
        slope_h.normalize()

        slide_h = LVector3f(float(self._slide_dir.x), float(self._slide_dir.y), 0.0)
        if slide_h.lengthSquared() <= 1e-12:
            return 0.0
        slide_h.normalize()

        align = float(slide_h.dot(slope_h))
        if abs(align) <= 1e-6:
            return 0.0

        slope_accel = float(self._motion_solver.gravity()) * slope_mag * 0.70
        return slope_accel * align * max(0.0, float(dt))

    def _apply_jump(self) -> None:
        self._set_vertical_velocity(
            self._jump_up_speed(),
            source=MotionWriteSource.IMPULSE,
            reason="jump.takeoff",
        )
        self._jump_buffer_timer = 0.0
        self.grounded = False
        self._coyote_timer = 0.0
        self._slide_active = False

    def _jump_up_speed(self) -> float:
        return float(self._motion_solver.jump_takeoff_speed())

    def _record_velocity_write(self, *, source: MotionWriteSource, reason: str) -> None:
        self._last_vel_write_source = str(source.value)
        self._last_vel_write_reason = str(reason)

    def _set_velocity(self, vel: LVector3f, *, source: MotionWriteSource, reason: str) -> None:
        self.vel = LVector3f(vel)
        self._record_velocity_write(source=source, reason=reason)

    def _set_horizontal_velocity(self, *, x: float, y: float, source: MotionWriteSource, reason: str) -> None:
        self.vel.x = float(x)
        self.vel.y = float(y)
        self._record_velocity_write(source=source, reason=reason)

    def _set_vertical_velocity(self, z: float, *, source: MotionWriteSource, reason: str) -> None:
        self.vel.z = float(z)
        self._record_velocity_write(source=source, reason=reason)

    def _add_velocity(self, delta: LVector3f, *, source: MotionWriteSource, reason: str) -> None:
        self.vel += LVector3f(delta)
        self._record_velocity_write(source=source, reason=reason)
