from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.common.aabb import AABB
from ivan.physics.collision_world import CollisionWorld
from ivan.physics.motion.intent import MotionIntent
from ivan.physics.motion.solver import MotionSolver
from ivan.physics.motion.state import MotionWriteSource
from ivan.physics.player_controller_actions import PlayerControllerActionsMixin
from ivan.physics.player_controller_collision import PlayerControllerCollisionMixin
from ivan.physics.player_controller_surf import PlayerControllerSurfMixin
from ivan.physics.tuning import PhysicsTuning


class PlayerController(PlayerControllerActionsMixin, PlayerControllerSurfMixin, PlayerControllerCollisionMixin):
    """Kinematic Quake3-style controller (step + slide) with optional Bullet sweep queries."""

    def __init__(
        self,
        *,
        tuning: PhysicsTuning,
        spawn_point: LVector3f,
        aabbs: list[AABB],
        collision: CollisionWorld | None,
    ) -> None:
        self.tuning = tuning
        self.spawn_point = LVector3f(spawn_point)
        self.aabbs = aabbs
        self.collision = collision

        self.pos = LVector3f(self.spawn_point)
        self.vel = LVector3f(0, 0, 0)
        self.player_half = LVector3f(tuning.player_radius, tuning.player_radius, tuning.player_half_height)
        self._standing_half_height = float(tuning.player_half_height)

        self.grounded = False
        self.crouched = False
        self._jump_buffer_timer = 0.0
        self._jump_pressed = False
        self._coyote_timer = 0.0
        self._slide_held = False
        self._slide_active = False
        self._slide_dir = LVector3f(0, 0, 0)
        self._contact_count = 0

        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._wall_contact_point = LVector3f(0, 0, 0)
        self._wallrun_active = False
        self._surf_contact_timer = 999.0
        self._surf_normal = LVector3f(0, 0, 0)
        self._wall_jump_lock_timer = 999.0
        self._vault_cooldown_timer = 999.0
        self._ground_normal = LVector3f(0, 0, 1)
        self._hitstop_active = False
        self._knockback_active = False
        self._grapple_attached = False
        self._grapple_anchor = LVector3f(0, 0, 0)
        self._grapple_length = 0.0
        self._grapple_attach_shorten_left = 0.0
        self._motion_solver = MotionSolver.from_tuning(tuning=self.tuning)
        self._last_vel_write_source = MotionWriteSource.EXTERNAL.value
        self._last_vel_write_reason = "init"

        self.apply_hull_settings()

    def apply_hull_settings(self) -> None:
        self._motion_solver.sync_from_tuning(tuning=self.tuning)
        self._standing_half_height = float(self.tuning.player_half_height)
        self.player_half.x = float(self.tuning.player_radius)
        self.player_half.y = float(self.tuning.player_radius)
        self.player_half.z = self._current_target_half_height()
        if self.collision is not None:
            self.collision.update_player_sweep_shape(
                player_radius=float(self.tuning.player_radius),
                player_half_height=float(self.player_half.z),
            )

    def respawn(self) -> None:
        self.pos = LVector3f(self.spawn_point)
        self._set_velocity(LVector3f(0, 0, 0), source=MotionWriteSource.EXTERNAL, reason="respawn")
        self.crouched = False
        self._coyote_timer = 0.0
        self._slide_active = False
        self._slide_held = False
        self._slide_dir = LVector3f(0, 0, 0)
        self._contact_count = 0
        self._wallrun_active = False
        self.detach_grapple()
        self.apply_hull_settings()

    def queue_jump(self) -> None:
        self._motion_solver.sync_from_tuning(tuning=self.tuning)
        if self.tuning.enable_jump_buffer and bool(self.tuning.coyote_buffer_enabled):
            self._jump_buffer_timer = float(self._motion_solver.input_buffer_time())
            return
        self._jump_pressed = True

    def queue_slide(self, *, wish_dir: LVector3f, yaw_deg: float) -> None:
        # Legacy edge-triggered helper kept for tests/callers.
        _ = wish_dir
        _ = yaw_deg
        self.set_slide_held(held=True)

    def set_slide_held(self, *, held: bool) -> None:
        self._slide_held = bool(held) and bool(self.tuning.slide_enabled)

    def can_ground_jump(self) -> bool:
        return self.grounded

    def is_sliding(self) -> bool:
        return bool(self._slide_active)

    def contact_count(self) -> int:
        return int(self._contact_count)

    def jump_buffer_left(self) -> float:
        return float(self._jump_buffer_timer)

    def coyote_left(self) -> float:
        return float(self._coyote_timer)

    def ground_normal(self) -> LVector3f:
        return LVector3f(self._ground_normal)

    def wall_normal(self) -> LVector3f:
        return LVector3f(self._wall_normal)

    def motion_state_name(self) -> str:
        if self._knockback_active:
            return "knockback"
        if self._hitstop_active:
            return "hitstop"
        if self.is_sliding():
            return "slide"
        if self.is_wallrunning():
            return "wallrun"
        return "ground" if bool(self.grounded) else "air"

    def last_velocity_write_source(self) -> str:
        return str(self._last_vel_write_source)

    def last_velocity_write_reason(self) -> str:
        return str(self._last_vel_write_reason)

    def set_external_velocity(self, *, vel: LVector3f, reason: str = "external") -> None:
        self._set_velocity(LVector3f(vel), source=MotionWriteSource.EXTERNAL, reason=str(reason))

    def set_hitstop_active(self, active: bool) -> None:
        self._hitstop_active = bool(active)

    def set_knockback_active(self, active: bool) -> None:
        self._knockback_active = bool(active)

    def is_wallrunning(self) -> bool:
        return bool(self._wallrun_active)

    def wallrun_camera_roll_deg(self, *, yaw_deg: float) -> float:
        if not self.is_wallrunning():
            return 0.0
        # Camera feedback should drop quickly after losing contact, even if wallrun physics
        # still has a short grace window.
        if self._wall_contact_timer > 0.055:
            return 0.0
        h_rad = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if forward.lengthSquared() <= 1e-12:
            return 0.0
        right = LVector3f(forward.y, -forward.x, 0.0)
        side = float(right.dot(self._wall_normal))
        if abs(side) <= 1e-12:
            return 0.0
        # Slight side roll away from the wall to indicate active wallrun.
        return math.copysign(6.0, side)

    def _has_wallrun_contact(self) -> bool:
        if not bool(self.tuning.wallrun_enabled):
            return False
        if self.grounded:
            return False
        if self._wall_contact_timer > 0.24:
            return False
        return self._wall_normal.lengthSquared() > 0.01

    def _can_coyote_jump(self) -> bool:
        if self.grounded:
            return True
        if not bool(self.tuning.coyote_buffer_enabled):
            return False
        return float(self._coyote_timer) > 0.0

    def has_wall_for_jump(self) -> bool:
        if self.grounded:
            return False
        if self._wall_contact_timer > 0.24 or self._wall_normal.lengthSquared() <= 0.01:
            return False
        return self._wall_jump_lock_timer >= float(self.tuning.wall_jump_cooldown)

    # NOTE: `crouching` remains for backward compatibility with tests/callers.
    # Runtime movement no longer consumes direct crouch input; low hull is slide-owned.
    def step(self, *, dt: float, wish_dir: LVector3f, yaw_deg: float, pitch_deg: float = 0.0, crouching: bool = False) -> None:
        _ = crouching
        dt = float(dt)
        self._motion_solver.sync_from_tuning(tuning=self.tuning)
        self._contact_count = 0
        self._wallrun_active = False
        self._wall_contact_timer += dt
        self._surf_contact_timer += dt
        self._wall_jump_lock_timer += dt
        self._vault_cooldown_timer += dt
        self._jump_buffer_timer = max(0.0, self._jump_buffer_timer - dt)
        self._refresh_wall_contact_from_probe()

        # Determine grounded state before applying friction/accel.
        if self.collision is not None:
            self._bullet_ground_trace()
        if self.grounded:
            self._coyote_timer = float(self._motion_solver.coyote_time())
        else:
            self._coyote_timer = max(0.0, float(self._coyote_timer) - dt)
            # Slide is a grounded state. Drop it immediately if we leave the floor.
            self._slide_active = False

        slide_wants_hold = bool(self._slide_held) and bool(self.grounded) and bool(self.tuning.slide_enabled)
        if not slide_wants_hold:
            self._slide_active = False
        elif not self._slide_active:
            self._start_slide(yaw_deg=yaw_deg)

        slide_active = self.is_sliding()
        self._update_slide_hull_state(slide_active)

        # While slide key is held, keyboard movement axes are ignored so slide remains inertia-driven.
        # This also prevents one-frame ground-contact flicker from reintroducing WASD influence.
        input_locked_for_slide = bool(self._slide_held)
        effective_wish = LVector3f(0.0, 0.0, 0.0) if input_locked_for_slide else LVector3f(wish_dir)
        has_move_input = self._horizontal_unit(effective_wish).lengthSquared() > 1e-12

        if self._knockback_active:
            # Priority lane: external knockback can override run/slide intent but keeps gravity.
            self._motion_solver.apply_gravity(vel=self.vel, dt=dt, gravity_scale=1.0)
        elif self._hitstop_active:
            # Explicitly paused motion state: gravity can be paused only in hitstop-like modes.
            pass
        elif slide_active:
            self._step_slide_mode(dt=dt, yaw_deg=yaw_deg)
        elif self.grounded:
            ground_jump_requested = self._consume_jump_request() and self.can_ground_jump()
            if ground_jump_requested:
                # Preserve carried horizontal speed on successful hop timing frames.
                self._apply_jump()
            else:
                # Keep Vmax authoritative while input is held; friction should primarily damp coasting.
                if not has_move_input:
                    self._apply_friction(dt)
                self._motion_solver.apply_ground_run(vel=self.vel, wish_dir=effective_wish, dt=dt, speed_scale=1.0)
        else:
            surf_active = self._has_recent_surf_contact_for_physics(dt)
            wallrun_active = self._has_wallrun_contact()
            self._wallrun_active = bool(wallrun_active)
            air_wish = LVector3f(effective_wish)
            air_accel = float(self._motion_solver.air_accel())
            air_speed = float(self._motion_solver.air_speed(speed_scale=1.0))
            if surf_active:
                # Redirect existing horizontal momentum onto the ramp plane so speed can naturally
                # exchange between horizontal and vertical components while surfing.
                self._redirect_surf_inertia(dt)
                # GoldSrc-like surf: still "air move", but wish direction gets constrained by ramp plane.
                air_wish = self._project_to_plane(effective_wish, self._surf_normal)
                air_accel *= max(0.0, float(self.tuning.surf_accel)) / 10.0
            # On surf ramps, keep the projected ramp-plane wish so momentum can redirect up/down slope.
            accel_wish = air_wish if surf_active else self._horizontal_unit(air_wish)
            if surf_active:
                self._accelerate_surf_redirect(accel_wish, air_speed, air_accel, dt)
            else:
                self._motion_solver.apply_air_accel(
                    vel=self.vel,
                    wish_dir=accel_wish,
                    dt=dt,
                    wish_speed=air_speed,
                    accel=air_accel,
                )

            gravity_scale = float(self.tuning.surf_gravity_scale) if surf_active else 1.0
            if surf_active and self.vel.z < 0.0:
                # Descending on surf should follow normal gravity, not surf-specific gravity tuning.
                gravity_scale = 1.0
            if wallrun_active:
                # Preserve upward jump carry, but reduce descent for longer wall traversal.
                gravity_scale = min(gravity_scale, 0.35)

            self._motion_solver.apply_gravity(vel=self.vel, dt=dt, gravity_scale=gravity_scale)
            if wallrun_active:
                self._motion_solver.apply_wallrun_sink(vel=self.vel, dt=dt)

            if self._consume_jump_request():
                if self._can_coyote_jump():
                    self._apply_jump()
                elif self.tuning.vault_enabled and self._try_vault(yaw_deg=yaw_deg):
                    pass
                elif self.tuning.walljump_enabled and self.has_wall_for_jump():
                    self._apply_wall_jump(
                        yaw_deg=yaw_deg,
                        pitch_deg=pitch_deg,
                        prefer_camera_forward=bool(wallrun_active),
                    )

        self._apply_grapple_constraint(dt=dt)

        # Movement + collision resolution.
        if self.collision is not None:
            self._bullet_step_slide_move(self.vel * dt)
            self._bullet_ground_snap()
            # Update grounded state after movement (e.g. walking off a ledge).
            self._bullet_ground_trace()
            self._refresh_wall_contact_from_probe()
        else:
            self._move_and_collide(self.vel * dt)

        self._enforce_grapple_length()

        if self.grounded:
            self._wall_jump_lock_timer = 999.0
            self._coyote_timer = float(self._motion_solver.coyote_time())
            self._wallrun_active = False

        self._update_slide_hull_state(self.is_sliding())

    def step_with_intent(self, *, dt: float, intent: MotionIntent, yaw_deg: float, pitch_deg: float = 0.0) -> None:
        if bool(intent.jump_requested):
            self.queue_jump()
        self.set_slide_held(
            held=bool(intent.slide_requested),
        )
        self.step(
            dt=dt,
            wish_dir=LVector3f(intent.wish_dir),
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
            crouching=False,
        )

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
        self._set_horizontal_velocity(
            x=float(self._slide_dir.x) * hspeed,
            y=float(self._slide_dir.y) * hspeed,
            source=MotionWriteSource.SOLVER,
            reason="slide.solve",
        )
        self._motion_solver.apply_gravity(vel=self.vel, dt=dt, gravity_scale=1.0)

        if self._consume_jump_request() and self._can_coyote_jump():
            self._apply_jump()

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
