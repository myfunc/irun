from __future__ import annotations

import math

from panda3d.core import LVector3f


class PlayerControllerActionsMixin:
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

    def _apply_wall_jump(self, *, yaw_deg: float, pitch_deg: float = 0.0, prefer_camera_forward: bool = False) -> None:
        away = LVector3f(self._wall_normal.x, self._wall_normal.y, 0)
        if away.lengthSquared() > 0.001:
            away.normalize()
        h_rad = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        if forward.lengthSquared() > 1e-12:
            forward.normalize()
        wjb = float(self.tuning.wall_jump_boost)
        if prefer_camera_forward:
            p_rad = math.radians(float(pitch_deg))
            view = LVector3f(
                -math.sin(h_rad) * math.cos(p_rad),
                math.cos(h_rad) * math.cos(p_rad),
                math.sin(p_rad),
            )
            view_h = LVector3f(view.x, view.y, 0.0)
            if view_h.lengthSquared() > 1e-12:
                view_h.normalize()
            else:
                view_h = LVector3f(forward)
            # Keep a guaranteed peel-away component from the wall while biasing jump direction to camera view.
            jump_dir = view_h * 0.72 + away * 0.28
            if jump_dir.lengthSquared() > 1e-12:
                jump_dir.normalize()
            else:
                jump_dir = LVector3f(away)
            boost = jump_dir * wjb
        else:
            boost = away * wjb + forward * (wjb * 0.45)
        self.vel.x = boost.x
        self.vel.y = boost.y
        self.vel.z = self._jump_up_speed() * 0.95
        self._wall_jump_lock_timer = 0.0
        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._jump_buffer_timer = 0.0
        self._dash_time_left = 0.0

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

        max_vault_hspeed = float(self._motion_solver.air_speed(speed_scale=1.0)) * 1.6
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
        if not bool(self.tuning.custom_friction_enabled):
            return
        speed = math.sqrt(self.vel.x * self.vel.x + self.vel.y * self.vel.y)
        if speed <= 0.0001:
            return
        self._motion_solver.apply_ground_coast_damping(vel=self.vel, dt=dt)

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
