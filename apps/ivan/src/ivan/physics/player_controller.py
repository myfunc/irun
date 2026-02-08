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
        self._jump_buffer_timer = 0.0
        self._jump_pressed = False

        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._wall_contact_point = LVector3f(0, 0, 0)
        self._surf_contact_timer = 999.0
        self._surf_normal = LVector3f(0, 0, 0)
        self._wall_jump_lock_timer = 999.0
        self._vault_cooldown_timer = 999.0
        self._ground_normal = LVector3f(0, 0, 1)
        self._grapple_attached = False
        self._grapple_anchor = LVector3f(0, 0, 0)
        self._grapple_length = 0.0
        self._grapple_attach_shorten_left = 0.0

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
        self.detach_grapple()
        self.apply_hull_settings()

    def queue_jump(self) -> None:
        if self.tuning.enable_jump_buffer:
            self._jump_buffer_timer = float(self.tuning.jump_buffer_time)
            return
        self._jump_pressed = True

    def can_ground_jump(self) -> bool:
        return self.grounded

    def has_wall_for_jump(self) -> bool:
        if self.grounded:
            return False
        if self._wall_contact_timer > 0.18 or self._wall_normal.lengthSquared() <= 0.01:
            return False
        return self._wall_jump_lock_timer >= float(self.tuning.wall_jump_cooldown)

    def attach_grapple(self, *, anchor: LVector3f) -> None:
        self._grapple_anchor = LVector3f(anchor)
        rope = self._grapple_anchor - self.pos
        rope_dist = float(rope.length())
        self._grapple_length = min(
            float(self.tuning.grapple_max_length),
            max(float(self.tuning.grapple_min_length), rope_dist),
        )
        self._grapple_attached = True
        self._grapple_attach_shorten_left = max(0.0, float(self.tuning.grapple_attach_shorten_time))
        if rope_dist > 1e-9:
            rope.normalize()
            self.vel += rope * max(0.0, float(self.tuning.grapple_attach_boost))

    def detach_grapple(self) -> None:
        self._grapple_attached = False
        self._grapple_attach_shorten_left = 0.0

    def is_grapple_attached(self) -> bool:
        return bool(self._grapple_attached) and bool(self.tuning.grapple_enabled)

    def grapple_anchor(self) -> LVector3f | None:
        if not self.is_grapple_attached():
            return None
        return LVector3f(self._grapple_anchor)

    def step(self, *, dt: float, wish_dir: LVector3f, yaw_deg: float, crouching: bool) -> None:
        dt = float(dt)
        self._update_crouch_state(crouching)
        self._wall_contact_timer += dt
        self._surf_contact_timer += dt
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
            surf_active = self._has_recent_surf_contact_for_physics(dt)
            air_wish = LVector3f(wish_dir)
            air_accel = float(self.tuning.jump_accel)
            if surf_active:
                # Redirect existing horizontal momentum onto the ramp plane so speed can naturally
                # exchange between horizontal and vertical components while surfing.
                self._redirect_surf_inertia(dt)
                # GoldSrc-like surf: still "air move", but wish direction gets constrained by ramp plane.
                air_wish = self._project_to_plane(wish_dir, self._surf_normal)
                air_accel *= max(0.0, float(self.tuning.surf_accel)) / 10.0
            # On surf ramps, keep the projected ramp-plane wish so momentum can redirect up/down slope.
            accel_wish = air_wish if surf_active else self._horizontal_unit(air_wish)

            counter_strafe = (not surf_active) and self._is_counter_strafe(accel_wish)
            if counter_strafe:
                # Opposite input in air should brake aggressively instead of accelerating backward.
                self._apply_air_counter_strafe_brake(accel_wish, dt)
            else:
                if surf_active:
                    self._accelerate_surf_redirect(accel_wish, float(self.tuning.max_air_speed), air_accel, dt)
                else:
                    self._accelerate(accel_wish, float(self.tuning.max_air_speed), air_accel, dt)
                self._air_control(accel_wish, dt)

            gravity_scale = float(self.tuning.surf_gravity_scale) if surf_active else 1.0
            if surf_active and self.vel.z < 0.0:
                # Descending on surf should follow normal gravity, not surf-specific gravity tuning.
                gravity_scale = 1.0
            if self.tuning.wallrun_enabled and self.has_wall_for_jump():
                # Preserve upward jump motion along walls, but reduce fall speed while descending.
                if self.vel.z <= 0.0:
                    gravity_scale = min(gravity_scale, 0.55)
                    self.vel.z = max(self.vel.z, -2.0)

            self.vel.z -= float(self.tuning.gravity) * gravity_scale * dt

            if self._consume_jump_request():
                if self.tuning.vault_enabled and self._try_vault(yaw_deg=yaw_deg):
                    pass
                elif self.tuning.walljump_enabled and self.has_wall_for_jump():
                    self._apply_wall_jump(yaw_deg=yaw_deg)

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
        if self._wall_contact_timer > 0.30 or self._wall_normal.lengthSquared() <= 0.01:
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

    def _apply_grapple_constraint(self, *, dt: float) -> None:
        if not self.is_grapple_attached():
            return

        if self._grapple_attach_shorten_left > 0.0:
            auto_speed = max(0.0, float(self.tuning.grapple_attach_shorten_speed))
            self._grapple_length = max(float(self.tuning.grapple_min_length), self._grapple_length - auto_speed * dt)
            self._grapple_attach_shorten_left = max(0.0, self._grapple_attach_shorten_left - dt)

        to_player = self.pos - self._grapple_anchor
        dist = float(to_player.length())
        if dist <= 1e-6 or dist <= self._grapple_length:
            return
        n = to_player / dist

        # Rope is taut: remove outward radial speed and add a pull to restore rope length.
        radial_out = float(self.vel.dot(n))
        if radial_out > 0.0:
            self.vel -= n * radial_out
        pull_max = max(0.0, float(self.tuning.grapple_pull_strength))
        pull = min(pull_max, max(0.0, (dist - self._grapple_length) / max(1e-5, dt)))
        self.vel -= n * pull

    def _enforce_grapple_length(self) -> None:
        if not self.is_grapple_attached():
            return
        to_player = self.pos - self._grapple_anchor
        dist = float(to_player.length())
        if dist <= 1e-6 or dist <= self._grapple_length:
            return
        n = to_player / dist
        self.pos = self._grapple_anchor + n * self._grapple_length
        radial_out = float(self.vel.dot(n))
        if radial_out > 0.0:
            self.vel -= n * radial_out

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

    def _accelerate_surf_redirect(self, wish_dir: LVector3f, wish_speed: float, accel: float, dt: float) -> None:
        if wish_dir.lengthSquared() <= 0.0:
            return
        horiz_factor = min(1.0, math.sqrt(wish_dir.x * wish_dir.x + wish_dir.y * wish_dir.y))
        if horiz_factor <= 1e-4:
            return
        effective_wish_speed = wish_speed * horiz_factor
        current_speed = self.vel.dot(wish_dir)
        add_speed = effective_wish_speed - current_speed
        if add_speed <= 0.0:
            return

        accel_speed = accel * dt * effective_wish_speed
        accel_speed = min(accel_speed, add_speed)
        if accel_speed <= 0.0:
            return

        delta = wish_dir * accel_speed

        # Prevent instant one-frame horizontal reversal while preserving perpendicular and vertical
        # redirection components so surf steering can still turn speed into height.
        pre_h = LVector3f(self.vel.x, self.vel.y, 0.0)
        if pre_h.lengthSquared() > 1e-12:
            post_h = LVector3f(pre_h.x + delta.x, pre_h.y + delta.y, 0.0)
            if pre_h.dot(post_h) < 0.0:
                pre_len = pre_h.length()
                if pre_len > 1e-12:
                    pre_h.normalize()
                    delta_along_pre = delta.x * pre_h.x + delta.y * pre_h.y
                    # Keep at least some carry each tick; steer should redirect momentum, not hard-stop it.
                    min_delta_along_pre = -(pre_len * 0.55)
                    if delta_along_pre < min_delta_along_pre:
                        correction = min_delta_along_pre - delta_along_pre
                        delta.x += pre_h.x * correction
                        delta.y += pre_h.y * correction

        # Input-driven surf acceleration can add uphill vertical, but must not force extra downhill pull.
        if delta.z < 0.0:
            delta.z = 0.0

        self.vel += delta

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

        # Pure tuning-based deceleration so the slider is authoritative.
        brake = max(0.0, float(self.tuning.air_counter_strafe_brake))
        strength = min(1.0, max(0.0, (-dot_now - 0.25) / 0.75))
        decel = brake * (0.55 + 0.45 * strength) * dt
        new_speed = max(0.0, speed - decel)
        self.vel.x = horiz.x * new_speed
        self.vel.y = horiz.y * new_speed

    def has_surf_surface(self) -> bool:
        return bool(self.tuning.surf_enabled) and self._surf_contact_timer <= 0.30 and self._surf_normal.lengthSquared() > 0.01

    def _has_recent_surf_contact_for_physics(self, dt: float) -> bool:
        if not bool(self.tuning.surf_enabled):
            return False
        if self._surf_normal.lengthSquared() <= 0.01:
            return False
        # Surf acceleration/gravity rules apply only while contact is fresh.
        # This prevents extra "post-leave" push/pull after sliding off a ramp.
        return self._surf_contact_timer <= max(0.0, float(dt) * 1.25)

    @staticmethod
    def _project_to_plane(vec: LVector3f, normal: LVector3f) -> LVector3f:
        n = LVector3f(normal)
        if n.lengthSquared() <= 1e-12:
            return LVector3f(vec)
        n.normalize()
        out = LVector3f(vec) - n * LVector3f(vec).dot(n)
        if out.lengthSquared() > 1e-12:
            out.normalize()
        return out

    @staticmethod
    def _horizontal_unit(vec: LVector3f) -> LVector3f:
        out = LVector3f(vec.x, vec.y, 0.0)
        if out.lengthSquared() > 1e-12:
            out.normalize()
        return out

    def _redirect_surf_inertia(self, dt: float) -> None:
        horiz = LVector3f(self.vel.x, self.vel.y, 0.0)
        horiz_speed = horiz.length()
        if horiz_speed <= 1e-6:
            return

        # Build a ramp-tangent direction that follows current horizontal travel heading.
        tangent = self._project_to_plane(horiz, self._surf_normal)
        if tangent.lengthSquared() <= 1e-12:
            return

        desired = tangent * horiz_speed
        current = LVector3f(horiz)

        # Fast blend keeps surf responsive while still preserving inertia feel.
        blend_rate = 7.0
        blend = min(1.0, max(0.0, blend_rate * float(dt)))
        self.vel += (desired - current) * blend

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
                    if not self._is_valid_wall_contact(point=p):
                        continue
                    return wall_n, p
        return LVector3f(0, 0, 0), LVector3f(0, 0, 0)

    def _is_valid_wall_contact(self, *, point: LVector3f) -> bool:
        feet_z = float(self.pos.z - self.player_half.z)
        min_height = max(0.12, min(0.65, float(self.tuning.step_height) + 0.05))
        return float(point.z) >= (feet_z + min_height)

    def _set_wall_contact(self, normal: LVector3f, point: LVector3f) -> None:
        self._wall_normal = LVector3f(normal.x, normal.y, 0.0)
        if self._wall_normal.lengthSquared() > 1e-12:
            self._wall_normal.normalize()
        self._wall_contact_point = LVector3f(point)
        self._wall_contact_timer = 0.0

    def _set_surf_contact(self, normal: LVector3f) -> None:
        self._surf_normal = LVector3f(normal)
        if self._surf_normal.lengthSquared() > 1e-12:
            self._surf_normal.normalize()
        self._surf_contact_timer = 0.0

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

    def _is_surf_normal(self, normal: LVector3f) -> bool:
        if not bool(self.tuning.surf_enabled):
            return False
        n = LVector3f(normal)
        if n.lengthSquared() <= 1e-12:
            return False
        n.normalize()
        min_z = max(0.01, min(0.95, float(self.tuning.surf_min_normal_z)))
        max_z = max(min_z, min(0.98, float(self.tuning.surf_max_normal_z)))
        return min_z <= n.z <= max_z

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
        if self._is_surf_normal(n):
            self._set_surf_contact(n)
            self.grounded = False
            return
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
            if self._is_surf_normal(n):
                self._set_surf_contact(n)
            elif n.z > walkable_z:
                self.grounded = True
                self._ground_normal = LVector3f(n)
                if self.vel.z < 0.0:
                    self.vel.z = 0.0
            elif abs(n.z) < 0.65:
                hit_pos = pos
                if hasattr(hit, "getHitPos"):
                    hit_pos = LVector3f(hit.getHitPos())
                if self._is_valid_wall_contact(point=hit_pos):
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
        if self._is_surf_normal(n):
            return
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
