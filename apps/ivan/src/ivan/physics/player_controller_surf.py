from __future__ import annotations

import math

from panda3d.core import LVector3f


class PlayerControllerSurfMixin:
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
