from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.common.aabb import AABB
from ivan.physics.collision_world import CollisionWorld
from ivan.physics.tuning import PhysicsTuning


class PlayerController:
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
        self._ground_timer = 0.0
        self._jump_buffer_timer = 0.0
        self._jump_pressed = False

        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._wall_contact_point = LVector3f(0, 0, 0)
        self._last_wall_jump_normal = LVector3f(0, 0, 0)
        self._last_wall_jump_point = LVector3f(0, 0, 0)
        self._wall_jump_lock_timer = 999.0
        self._vault_cooldown_timer = 999.0
        self._ground_normal = LVector3f(0, 0, 1)
        self._prev_wish_dir = LVector3f(0, 0, 0)

        self.apply_hull_settings()

    def apply_hull_settings(self) -> None:
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
        self.apply_hull_settings()

    def queue_jump(self) -> None:
        if self.tuning.enable_jump_buffer:
            self._jump_buffer_timer = float(self.tuning.jump_buffer_time)
            return
        self._jump_pressed = True

    def can_ground_jump(self) -> bool:
        if self.grounded:
            return True
        return bool(self.tuning.enable_coyote) and self._ground_timer <= float(self.tuning.coyote_time)

    def has_wall_for_jump(self) -> bool:
        if self._wall_contact_timer > 0.18 or self._wall_normal.lengthSquared() <= 0.01:
            return False
        n = LVector3f(self._wall_normal)
        l = LVector3f(self._last_wall_jump_normal)
        if n.lengthSquared() > 1e-12:
            n.normalize()
        if l.lengthSquared() > 1e-12:
            l.normalize()
        # Disallow repeated wall-jumps off the same wall plane in a row.
        if l.lengthSquared() <= 1e-12:
            return True
        same_plane = n.dot(l) > 0.9
        if not same_plane:
            return True
        plane_d = l.dot(self._last_wall_jump_point)
        dist = abs(l.dot(self._wall_contact_point) - plane_d)
        return dist > 0.45

    def apply_grapple_impulse(self, *, yaw_deg: float) -> None:
        if not self.tuning.grapple_enabled:
            return
        h_rad = math.radians(yaw_deg)
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        self.vel += forward * 4.5 + LVector3f(0, 0, 1.8)

    def step(self, *, dt: float, wish_dir: LVector3f, yaw_deg: float, crouching: bool) -> None:
        dt = float(dt)
        self._update_crouch_state(crouching)
        self._wall_contact_timer += dt
        self._wall_jump_lock_timer += dt
        self._vault_cooldown_timer += dt
        self._jump_buffer_timer = max(0.0, self._jump_buffer_timer - dt)
        self._refresh_wall_contact_from_probe()

        # Determine grounded state before applying friction/accel (otherwise friction appears to "break"
        # whenever you don't happen to collide with the floor during this frame).
        if self.collision is not None:
            self._bullet_ground_trace()

        speed_scale = float(self.tuning.crouch_speed_multiplier) if self.crouched else 1.0
        target_ground_speed = float(self.tuning.max_ground_speed) * speed_scale

        if self.grounded:
            self._apply_friction(dt)
            self._accelerate(wish_dir, target_ground_speed, float(self.tuning.ground_accel), dt)
            if self._consume_jump_request() and self.can_ground_jump():
                self._apply_jump()
        else:
            counter_strafe = self._is_counter_strafe(wish_dir)
            if counter_strafe:
                # Opposite input in air should brake aggressively instead of accelerating backward.
                self._apply_air_counter_strafe_brake(wish_dir, dt)
            else:
                self._accelerate(wish_dir, float(self.tuning.max_air_speed), float(self.tuning.jump_accel), dt)
                self._air_control(wish_dir, dt)

            gravity_scale = 1.0
            if self.tuning.wallrun_enabled and self.has_wall_for_jump():
                # Preserve upward jump motion along walls, but reduce fall speed while descending.
                if self.vel.z <= 0.0:
                    gravity_scale = 0.55
                    self.vel.z = max(self.vel.z, -2.0)

            self.vel.z -= float(self.tuning.gravity) * gravity_scale * dt

            if self._consume_jump_request():
                if self.tuning.vault_enabled and self._try_vault(yaw_deg=yaw_deg):
                    pass
                elif self.tuning.walljump_enabled and self.has_wall_for_jump():
                    self._apply_wall_jump(yaw_deg=yaw_deg)

        # Movement + collision resolution.
        if self.collision is not None:
            self._bullet_step_slide_move(self.vel * dt)
            self._bullet_ground_snap()
            # Update grounded state after movement (e.g. walking off a ledge).
            self._bullet_ground_trace()
            self._refresh_wall_contact_from_probe()
        else:
            self._move_and_collide(self.vel * dt)

        if not self.grounded:
            self._ground_timer += dt
        else:
            self._ground_timer = 0.0
            self._last_wall_jump_normal = LVector3f(0, 0, 0)
            self._last_wall_jump_point = LVector3f(0, 0, 0)
            self._wall_jump_lock_timer = 999.0

        if wish_dir.lengthSquared() > 0.0:
            self._prev_wish_dir = LVector3f(wish_dir.x, wish_dir.y, 0.0)
        else:
            self._prev_wish_dir = LVector3f(0, 0, 0)

    def _consume_jump_request(self) -> bool:
        if self._jump_pressed:
            self._jump_pressed = False
            return True
        return self._jump_buffer_timer > 0.0

    def _apply_jump(self) -> None:
        self.vel.z = self._jump_up_speed()
        self._jump_buffer_timer = 0.0
        self.grounded = False

    def _apply_wall_jump(self, *, yaw_deg: float) -> None:
        away = LVector3f(self._wall_normal.x, self._wall_normal.y, 0)
        if away.lengthSquared() > 0.001:
            away.normalize()
        h_rad = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        wjb = float(self.tuning.wall_jump_boost)
        boost = away * wjb + forward * (wjb * 0.45)
        self.vel.x = boost.x
        self.vel.y = boost.y
        self.vel.z = self._jump_up_speed() * 0.95
        self._last_wall_jump_normal = LVector3f(away)
        self._last_wall_jump_point = LVector3f(self._wall_contact_point)
        self._wall_jump_lock_timer = 0.0
        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._jump_buffer_timer = 0.0

    def _jump_up_speed(self) -> float:
        g = max(0.001, float(self.tuning.gravity))
        h = max(0.01, float(self.tuning.jump_height))
        return math.sqrt(2.0 * g * h)

    def _try_vault(self, *, yaw_deg: float) -> bool:
        if self.collision is None:
            return False
        if self._vault_cooldown_timer < float(self.tuning.vault_cooldown):
            return False
        if self._wall_contact_timer > 0.16 or self._wall_normal.lengthSquared() <= 0.01:
            return False

        edge_z = self._find_vault_edge_height()
        if edge_z is None:
            return False

        feet_z = self.pos.z - self.player_half.z
        ledge_delta = edge_z - feet_z
        if ledge_delta < float(self.tuning.vault_min_ledge_height):
            return False
        if ledge_delta > float(self.tuning.vault_max_ledge_height):
            return False
        if feet_z >= edge_z - 0.02:
            return False

        self._apply_vault(yaw_deg=yaw_deg)
        return True

    def _find_vault_edge_height(self) -> float | None:
        if self.collision is None:
            return None
        wall_n = LVector3f(self._wall_normal)
        if wall_n.lengthSquared() <= 1e-12:
            return None
        wall_n.normalize()

        feet_z = self.pos.z - self.player_half.z
        probe_xy = self.pos - wall_n * (self.player_half.x + 0.18)
        scan_top = feet_z + float(self.tuning.vault_max_ledge_height) + 0.35
        scan_bottom = feet_z - 0.25
        start = LVector3f(probe_xy.x, probe_xy.y, scan_top)
        end = LVector3f(probe_xy.x, probe_xy.y, scan_bottom)
        hit = self._bullet_sweep_closest(start, end)
        if not hit.hasHit():
            return None

        n = LVector3f(hit.getHitNormal())
        if n.lengthSquared() > 1e-12:
            n.normalize()
        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))
        if n.z <= walkable_z:
            return None

        return self._hit_z(hit=hit, start=start, end=end)

    @staticmethod
    def _hit_z(*, hit, start: LVector3f, end: LVector3f) -> float:
        if hasattr(hit, "getHitPos"):
            return float(LVector3f(hit.getHitPos()).z)
        frac = max(0.0, min(1.0, float(hit.getHitFraction())))
        return float((start + (end - start) * frac).z)

    def _apply_vault(self, *, yaw_deg: float) -> None:
        h_rad = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        if forward.lengthSquared() > 1e-12:
            forward.normalize()

        self.vel.z = max(self.vel.z, self._jump_up_speed() * float(self.tuning.vault_jump_multiplier))
        self.vel.x += forward.x * float(self.tuning.vault_forward_boost)
        self.vel.y += forward.y * float(self.tuning.vault_forward_boost)

        max_vault_hspeed = float(self.tuning.max_air_speed) * 1.6
        hspeed = math.sqrt(self.vel.x * self.vel.x + self.vel.y * self.vel.y)
        if hspeed > max_vault_hspeed and hspeed > 1e-9:
            s = max_vault_hspeed / hspeed
            self.vel.x *= s
            self.vel.y *= s

        self._vault_cooldown_timer = 0.0
        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._jump_buffer_timer = 0.0

    def _apply_friction(self, dt: float) -> None:
        speed = math.sqrt(self.vel.x * self.vel.x + self.vel.y * self.vel.y)
        if speed <= 0.0001:
            return
        drop = speed * float(self.tuning.friction) * dt
        new_speed = max(0.0, speed - drop)
        if new_speed == speed:
            return
        scale = new_speed / speed
        self.vel.x *= scale
        self.vel.y *= scale

    def _current_target_half_height(self) -> float:
        stand_h = max(0.15, float(self._standing_half_height))
        if self.crouched and self.tuning.crouch_enabled:
            return min(stand_h, max(0.15, float(self.tuning.crouch_half_height)))
        return stand_h

    def _update_crouch_state(self, crouching: bool) -> None:
        if not self.tuning.crouch_enabled:
            crouching = False

        target = bool(crouching)
        if target == self.crouched:
            return
        if target:
            self._apply_crouch_hull(True)
            self.crouched = True
            return

        if self._can_uncrouch():
            self._apply_crouch_hull(False)
            self.crouched = False

    def _apply_crouch_hull(self, crouched: bool) -> None:
        old_half = float(self.player_half.z)
        stand_h = max(0.15, float(self._standing_half_height))
        crouch_h = min(stand_h, max(0.15, float(self.tuning.crouch_half_height)))
        new_half = crouch_h if crouched else stand_h
        if abs(new_half - old_half) < 1e-6:
            return

        self.player_half.z = new_half
        self.pos.z -= old_half - new_half
        if self.collision is not None:
            self.collision.update_player_sweep_shape(
                player_radius=float(self.tuning.player_radius),
                player_half_height=float(new_half),
            )

    def _can_uncrouch(self) -> bool:
        if self.collision is None:
            return True
        stand_h = max(0.15, float(self._standing_half_height))
        if stand_h <= self.player_half.z + 1e-6:
            return True

        from_pos = LVector3f(self.pos)
        to_pos = LVector3f(self.pos.x, self.pos.y, self.pos.z + (stand_h - self.player_half.z))
        old_half = float(self.player_half.z)
        old_pos = LVector3f(self.pos)

        self.player_half.z = stand_h
        self.pos = LVector3f(to_pos)
        self.collision.update_player_sweep_shape(
            player_radius=float(self.tuning.player_radius),
            player_half_height=float(stand_h),
        )
        hit = self._bullet_sweep_closest(from_pos, to_pos)

        self.player_half.z = old_half
        self.pos = old_pos
        self.collision.update_player_sweep_shape(
            player_radius=float(self.tuning.player_radius),
            player_half_height=float(old_half),
        )

        return not hit.hasHit()

    def _accelerate(self, wish_dir: LVector3f, wish_speed: float, accel: float, dt: float) -> None:
        if wish_dir.lengthSquared() <= 0.0:
            return
        current_speed = self.vel.dot(wish_dir)
        add_speed = wish_speed - current_speed
        if add_speed <= 0:
            return
        accel_speed = accel * dt * wish_speed
        if accel_speed > add_speed:
            accel_speed = add_speed
        self.vel += wish_dir * accel_speed

    def _air_control(self, wish_dir: LVector3f, dt: float) -> None:
        if wish_dir.lengthSquared() <= 0.0:
            return
        steer = float(self.tuning.air_control) * dt
        self.vel.x += wish_dir.x * steer
        self.vel.y += wish_dir.y * steer

    def _is_counter_strafe(self, wish_dir: LVector3f) -> bool:
        horiz = LVector3f(self.vel.x, self.vel.y, 0)
        speed = horiz.length()
        if speed <= 0.01 or wish_dir.lengthSquared() <= 0.0:
            return False
        horiz.normalize()
        return horiz.dot(wish_dir) < -0.25

    def _apply_air_counter_strafe_brake(self, wish_dir: LVector3f, dt: float) -> None:
        horiz = LVector3f(self.vel.x, self.vel.y, 0)
        speed = horiz.length()
        if speed <= 0.01 or wish_dir.lengthSquared() <= 0.0:
            return
        horiz.normalize()
        dot_now = horiz.dot(wish_dir)
        if dot_now > -0.25:
            return

        prev = LVector3f(self._prev_wish_dir)
        was_opposite = False
        if prev.lengthSquared() > 1e-12:
            prev.normalize()
            was_opposite = horiz.dot(prev) < -0.25

        # Aggressive air braking with no reverse acceleration.
        bonus = speed * (14.0 if not was_opposite else 10.0) * dt
        decel = float(self.tuning.air_counter_strafe_brake) * dt + bonus
        new_speed = max(0.0, speed - decel)
        self.vel.x = horiz.x * new_speed
        self.vel.y = horiz.y * new_speed

    def _refresh_wall_contact_from_probe(self) -> None:
        n, p = self._probe_nearby_wall()
        if n.lengthSquared() <= 1e-12:
            return
        self._set_wall_contact(n, p)

    def _probe_nearby_wall(self) -> tuple[LVector3f, LVector3f]:
        if self.collision is None:
            return LVector3f(0, 0, 0), LVector3f(0, 0, 0)

        probe_dist = max(0.08, float(self.tuning.player_radius) + 0.06)
        directions = (
            LVector3f(1, 0, 0),
            LVector3f(-1, 0, 0),
            LVector3f(0, 1, 0),
            LVector3f(0, -1, 0),
        )
        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))

        for d in directions:
            hit = self._bullet_sweep_closest(self.pos, self.pos + d * probe_dist)
            if not hit.hasHit():
                continue
            n = LVector3f(hit.getHitNormal())
            if n.lengthSquared() > 1e-12:
                n.normalize()
            # Treat near-vertical surfaces as walls.
            if abs(n.z) < max(0.65, walkable_z):
                wall_n = LVector3f(n.x, n.y, 0.0)
                if wall_n.lengthSquared() > 1e-12:
                    wall_n.normalize()
                    frac = max(0.0, min(1.0, float(hit.getHitFraction())))
                    p = self.pos + d * (probe_dist * frac)
                    if hasattr(hit, "getHitPos"):
                        p = LVector3f(hit.getHitPos())
                    return wall_n, p
        return LVector3f(0, 0, 0), LVector3f(0, 0, 0)

    def _set_wall_contact(self, normal: LVector3f, point: LVector3f) -> None:
        self._wall_normal = LVector3f(normal.x, normal.y, 0.0)
        if self._wall_normal.lengthSquared() > 1e-12:
            self._wall_normal.normalize()
        self._wall_contact_point = LVector3f(point)
        self._wall_contact_timer = 0.0

    def _player_aabb(self) -> AABB:
        return AABB(self.pos - self.player_half, self.pos + self.player_half)

    @staticmethod
    def _overlap(a: AABB, b: AABB) -> bool:
        eps = 1e-4
        return (
            a.minimum.x < (b.maximum.x - eps)
            and a.maximum.x > (b.minimum.x + eps)
            and a.minimum.y < (b.maximum.y - eps)
            and a.maximum.y > (b.minimum.y + eps)
            and a.minimum.z < (b.maximum.z - eps)
            and a.maximum.z > (b.minimum.z + eps)
        )

    @staticmethod
    def _walkable_threshold_z(max_slope_deg: float) -> float:
        # Equivalent to Quake3 MIN_WALK_NORMAL (0.7) when max_slope_deg ~= 45.57.
        return float(math.cos(math.radians(max_slope_deg)))

    @staticmethod
    def _clip_velocity(vel: LVector3f, normal: LVector3f, overbounce: float = 1.001) -> LVector3f:
        # Quake-style clip against a collision plane.
        v = LVector3f(vel)
        n = LVector3f(normal)
        if n.lengthSquared() > 1e-12:
            n.normalize()
        backoff = v.dot(n)
        if backoff < 0.0:
            backoff *= overbounce
        else:
            backoff /= overbounce
        v -= n * backoff
        # Avoid tiny oscillations.
        if abs(v.x) < 1e-6:
            v.x = 0.0
        if abs(v.y) < 1e-6:
            v.y = 0.0
        if abs(v.z) < 1e-6:
            v.z = 0.0
        return v

    def _choose_clip_normal(self, normal: LVector3f) -> LVector3f:
        n = LVector3f(normal)
        if n.lengthSquared() > 1e-12:
            n.normalize()
        # Preserve upward jump movement when hugging mostly vertical walls/corners.
        if not self.grounded and self.vel.z > 0.0 and abs(n.z) < 0.82 and n.z > -0.35:
            wall_n = LVector3f(n.x, n.y, 0.0)
            if wall_n.lengthSquared() > 1e-12:
                wall_n.normalize()
                return wall_n
        return n

    def _bullet_sweep_closest(self, from_pos: LVector3f, to_pos: LVector3f):
        assert self.collision is not None
        return self.collision.sweep_closest(from_pos, to_pos)

    def _bullet_ground_trace(self) -> None:
        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))
        down = LVector3f(0, 0, -max(0.06, float(self.tuning.ground_snap_dist)))
        hit = self._bullet_sweep_closest(self.pos, self.pos + down)
        if not hit.hasHit():
            self.grounded = False
            return

        n = LVector3f(hit.getHitNormal())
        if n.lengthSquared() > 1e-12:
            n.normalize()
        self._ground_normal = n
        self.grounded = n.z > walkable_z

    def _bullet_slide_move(self, delta: LVector3f) -> None:
        # Iterative slide move (Quake-style): sweep -> move -> clip velocity -> repeat.
        if delta.lengthSquared() <= 1e-12:
            return

        pos = LVector3f(self.pos)
        remaining = LVector3f(delta)
        planes: list[LVector3f] = []

        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))
        skin = 0.006

        for _ in range(4):
            if remaining.lengthSquared() <= 1e-10:
                break

            move = LVector3f(remaining)
            target = pos + move
            hit = self._bullet_sweep_closest(pos, target)
            if not hit.hasHit():
                pos = target
                break

            hit_frac = max(0.0, min(1.0, float(hit.getHitFraction())))
            # Move to contact (slightly before), then push out along normal (skin).
            pos = pos + move * max(0.0, hit_frac - 1e-4)

            n = LVector3f(hit.getHitNormal())
            if n.lengthSquared() > 1e-12:
                n.normalize()
            planes.append(n)
            pos = pos + n * skin

            # Contact classification.
            if n.z > walkable_z:
                self.grounded = True
                self._ground_normal = LVector3f(n)
                if self.vel.z < 0.0:
                    self.vel.z = 0.0
            elif abs(n.z) < 0.65:
                hit_pos = pos
                if hasattr(hit, "getHitPos"):
                    hit_pos = LVector3f(hit.getHitPos())
                self._set_wall_contact(LVector3f(n.x, n.y, 0.0), hit_pos)
            elif n.z < -0.65 and self.vel.z > 0.0:
                # Ceiling.
                self.vel.z = 0.0

            clip_n = self._choose_clip_normal(n)
            if self.vel.dot(clip_n) < 0.0:
                self.vel = self._clip_velocity(self.vel, clip_n)
            time_left = 1.0 - hit_frac
            remaining = move * time_left
            if remaining.dot(clip_n) < 0.0:
                remaining = self._clip_velocity(remaining, clip_n, overbounce=1.0)

            # Multi-plane clip: if we're still going into any previous plane, clip again.
            for p in planes[:-1]:
                clip_p = self._choose_clip_normal(p)
                if remaining.dot(clip_p) < 0.0:
                    remaining = self._clip_velocity(remaining, clip_p, overbounce=1.0)
                if self.vel.dot(clip_p) < 0.0:
                    self.vel = self._clip_velocity(self.vel, clip_p)

        self.pos = pos

    def _bullet_step_slide_move(self, delta: LVector3f) -> None:
        # StepSlideMove: try regular slide; then try stepping up and sliding; choose the best.
        if delta.lengthSquared() <= 1e-12:
            return
        if not self.grounded:
            # Do not perform step-up in air; otherwise vertical walls can feel like ladders.
            self._bullet_slide_move(delta)
            return

        start_pos = LVector3f(self.pos)
        start_vel = LVector3f(self.vel)

        # First attempt: plain slide.
        self._bullet_slide_move(delta)
        pos1 = LVector3f(self.pos)
        vel1 = LVector3f(self.vel)

        # Second attempt: step up, move horizontally, then step down.
        self.pos = LVector3f(start_pos)
        self.vel = LVector3f(start_vel)

        step_up = LVector3f(0, 0, float(self.tuning.step_height))
        hit_up = self._bullet_sweep_closest(self.pos, self.pos + step_up)
        if not hit_up.hasHit():
            self.pos += step_up
            horiz = LVector3f(float(delta.x), float(delta.y), 0.0)
            self._bullet_slide_move(horiz)

            step_down = LVector3f(0, 0, -float(self.tuning.step_height) - 0.01)
            hit_down = self._bullet_sweep_closest(self.pos, self.pos + step_down)
            if hit_down.hasHit():
                frac = max(0.0, float(hit_down.getHitFraction()) - 1e-4)
                self.pos = self.pos + step_down * frac

        pos2 = LVector3f(self.pos)
        vel2 = LVector3f(self.vel)

        d1 = (pos1 - start_pos)
        d2 = (pos2 - start_pos)
        dist1 = d1.x * d1.x + d1.y * d1.y
        dist2 = d2.x * d2.x + d2.y * d2.y

        if dist1 >= dist2:
            self.pos = pos1
            self.vel = vel1
        else:
            self.pos = pos2
            self.vel = vel2

    def _bullet_ground_snap(self) -> None:
        # Keep the player glued to ground on small descents (Quake-style ground snap).
        if self.vel.z > 0.0:
            return

        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))
        down = LVector3f(0, 0, -float(self.tuning.ground_snap_dist))
        hit = self._bullet_sweep_closest(self.pos, self.pos + down)
        if not hit.hasHit():
            return
        n = LVector3f(hit.getHitNormal())
        if n.lengthSquared() > 1e-12:
            n.normalize()
        if n.z <= walkable_z:
            return

        frac = max(0.0, float(hit.getHitFraction()) - 1e-4)
        self.pos = self.pos + down * frac
        self.grounded = True
        self._ground_normal = LVector3f(n)
        if self.vel.z < 0.0:
            self.vel.z = 0.0

    def _move_and_collide(self, delta: LVector3f) -> None:
        self.grounded = False
        max_component = max(abs(delta.x), abs(delta.y), abs(delta.z))
        steps = max(1, int(math.ceil(max_component / 0.35)))
        step = delta / float(steps)

        for _ in range(steps):
            self.pos.x += step.x
            self._resolve_axis("x", step.x)

            self.pos.y += step.y
            self._resolve_axis("y", step.y)

            self.pos.z += step.z
            self._resolve_axis("z", step.z)

    def _resolve_axis(self, axis: str, delta: float) -> None:
        if abs(delta) < 1e-7:
            return

        paabb = self._player_aabb()
        for box in self.aabbs:
            if not self._overlap(paabb, box):
                continue

            if axis in ("x", "y"):
                z_overlap = min(paabb.maximum.z, box.maximum.z) - max(paabb.minimum.z, box.minimum.z)
                # Ignore almost-flat contact so floor standing does not become side collision.
                if z_overlap <= 0.08:
                    continue

            if axis == "x":
                if delta > 0:
                    self.pos.x = box.minimum.x - self.player_half.x
                    self._wall_normal = LVector3f(-1, 0, 0)
                else:
                    self.pos.x = box.maximum.x + self.player_half.x
                    self._wall_normal = LVector3f(1, 0, 0)
                self.vel.x = 0
                self._wall_contact_timer = 0.0
            elif axis == "y":
                if delta > 0:
                    self.pos.y = box.minimum.y - self.player_half.y
                    self._wall_normal = LVector3f(0, -1, 0)
                else:
                    self.pos.y = box.maximum.y + self.player_half.y
                    self._wall_normal = LVector3f(0, 1, 0)
                self.vel.y = 0
                self._wall_contact_timer = 0.0
            else:
                if delta > 0:
                    self.pos.z = box.minimum.z - self.player_half.z
                else:
                    self.pos.z = box.maximum.z + self.player_half.z
                    self.grounded = True
                self.vel.z = 0

            paabb = self._player_aabb()
