from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.common.aabb import AABB
from ivan.physics.collision_world import CollisionWorld
from ivan.physics.motion.intent import MotionIntent
from ivan.physics.motion.solver import MotionSolver
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
        self._dash_pressed = False
        self._dash_time_left = 0.0
        self._dash_dir = LVector3f(0, 0, 0)
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
        self._grapple_attached = False
        self._grapple_anchor = LVector3f(0, 0, 0)
        self._grapple_length = 0.0
        self._grapple_attach_shorten_left = 0.0
        self._motion_solver = MotionSolver.from_tuning(tuning=self.tuning)

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
        self.vel = LVector3f(0, 0, 0)
        self.crouched = False
        self._coyote_timer = 0.0
        self._dash_time_left = 0.0
        self._dash_pressed = False
        self._dash_dir = LVector3f(0, 0, 0)
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

    def queue_dash(self, *, wish_dir: LVector3f, yaw_deg: float) -> None:
        if not bool(self.tuning.dash_enabled):
            return
        direction = self._horizontal_unit(LVector3f(wish_dir))
        if direction.lengthSquared() <= 1e-12:
            h_rad = math.radians(float(yaw_deg))
            direction = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
            if direction.lengthSquared() > 1e-12:
                direction.normalize()
        if direction.lengthSquared() <= 1e-12:
            return
        self._dash_dir = direction
        self._dash_pressed = True

    def can_ground_jump(self) -> bool:
        return self.grounded

    def is_dashing(self) -> bool:
        return float(self._dash_time_left) > 0.0

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
        if self.is_dashing():
            return "dash"
        if self.is_wallrunning():
            return "wallrun"
        return "ground" if bool(self.grounded) else "air"

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

    def step(self, *, dt: float, wish_dir: LVector3f, yaw_deg: float, pitch_deg: float = 0.0, crouching: bool) -> None:
        dt = float(dt)
        self._motion_solver.sync_from_tuning(tuning=self.tuning)
        self._contact_count = 0
        self._wallrun_active = False
        self._update_crouch_state(crouching)
        self._wall_contact_timer += dt
        self._surf_contact_timer += dt
        self._wall_jump_lock_timer += dt
        self._vault_cooldown_timer += dt
        self._jump_buffer_timer = max(0.0, self._jump_buffer_timer - dt)
        self._dash_time_left = max(0.0, self._dash_time_left - dt)
        self._refresh_wall_contact_from_probe()

        # Determine grounded state before applying friction/accel (otherwise friction appears to "break"
        # whenever you don't happen to collide with the floor during this frame).
        if self.collision is not None:
            self._bullet_ground_trace()
        if self.grounded:
            self._coyote_timer = float(self._motion_solver.coyote_time())
        else:
            self._coyote_timer = max(0.0, float(self._coyote_timer) - dt)

        if self._consume_dash_request():
            self._start_dash(yaw_deg=yaw_deg, wish_dir=wish_dir)

        dash_active = self.is_dashing()
        speed_scale = float(self.tuning.crouch_speed_multiplier) if self.crouched else 1.0
        has_move_input = self._horizontal_unit(LVector3f(wish_dir)).lengthSquared() > 1e-12

        if dash_active:
            dash_speed = float(self._motion_solver.dash_speed())
            self.vel.x = float(self._dash_dir.x) * dash_speed
            self.vel.y = float(self._dash_dir.y) * dash_speed
            # Gravity always applies unless explicitly paused.
            self._motion_solver.apply_gravity(vel=self.vel, dt=dt, gravity_scale=1.0)
            if self._consume_jump_request() and self._can_coyote_jump():
                self._apply_jump()
        elif self.grounded:
            ground_jump_requested = self._consume_jump_request() and self.can_ground_jump()
            if ground_jump_requested:
                # Preserve carried horizontal speed on successful hop timing frames.
                self._apply_jump()
            else:
                # Keep Vmax authoritative while input is held; friction should primarily damp coasting.
                if not has_move_input:
                    self._apply_friction(dt)
                self._motion_solver.apply_ground_run(vel=self.vel, wish_dir=wish_dir, dt=dt, speed_scale=speed_scale)
        else:
            surf_active = self._has_recent_surf_contact_for_physics(dt)
            wallrun_active = self._has_wallrun_contact()
            self._wallrun_active = bool(wallrun_active)
            air_wish = LVector3f(wish_dir)
            air_accel = float(self._motion_solver.air_accel())
            air_speed = float(self._motion_solver.air_speed(speed_scale=speed_scale))
            if surf_active:
                # Redirect existing horizontal momentum onto the ramp plane so speed can naturally
                # exchange between horizontal and vertical components while surfing.
                self._redirect_surf_inertia(dt)
                # GoldSrc-like surf: still "air move", but wish direction gets constrained by ramp plane.
                air_wish = self._project_to_plane(wish_dir, self._surf_normal)
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
            if dash_active and bool(self.tuning.dash_sweep_enabled):
                self._bullet_dash_sweep_move(self.vel * dt)
            else:
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

    def step_with_intent(self, *, dt: float, intent: MotionIntent, yaw_deg: float, pitch_deg: float = 0.0) -> None:
        if bool(intent.jump_requested):
            self.queue_jump()
        if bool(intent.dash_requested):
            self.queue_dash(wish_dir=LVector3f(intent.wish_dir), yaw_deg=yaw_deg)
        self.step(
            dt=dt,
            wish_dir=LVector3f(intent.wish_dir),
            yaw_deg=yaw_deg,
            pitch_deg=pitch_deg,
            crouching=bool(intent.crouching),
        )

    def _consume_jump_request(self) -> bool:
        if self._jump_pressed:
            self._jump_pressed = False
            return True
        if not bool(self.tuning.coyote_buffer_enabled):
            return False
        return self._jump_buffer_timer > 0.0

    def _consume_dash_request(self) -> bool:
        if not self._dash_pressed:
            return False
        self._dash_pressed = False
        return bool(self.tuning.dash_enabled)

    def _start_dash(self, *, yaw_deg: float, wish_dir: LVector3f) -> None:
        if self._dash_time_left > 0.0:
            return
        dash_dir = self._horizontal_unit(LVector3f(wish_dir))
        if dash_dir.lengthSquared() <= 1e-12:
            h_rad = math.radians(float(yaw_deg))
            dash_dir = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if dash_dir.lengthSquared() <= 1e-12:
            return
        dash_dir.normalize()
        self._dash_dir = dash_dir
        self._dash_time_left = max(0.0, float(self._motion_solver.config.invariants.dash_duration))

    def _apply_jump(self) -> None:
        self.vel.z = self._jump_up_speed()
        self._jump_buffer_timer = 0.0
        self.grounded = False
        self._coyote_timer = 0.0
        self._dash_time_left = 0.0

    def _jump_up_speed(self) -> float:
        return float(self._motion_solver.jump_takeoff_speed())
