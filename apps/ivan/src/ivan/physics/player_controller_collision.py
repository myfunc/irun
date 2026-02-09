from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.common.aabb import AABB
from ivan.physics.motion.state import MotionWriteSource


class PlayerControllerCollisionMixin:
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
            self._contact_count += 1

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
                    self._set_vertical_velocity(0.0, source=MotionWriteSource.COLLISION, reason="slide.floor_stop")
            elif abs(n.z) < 0.65:
                hit_pos = pos
                if hasattr(hit, "getHitPos"):
                    hit_pos = LVector3f(hit.getHitPos())
                if self._is_valid_wall_contact(point=hit_pos):
                    self._set_wall_contact(LVector3f(n.x, n.y, 0.0), hit_pos)
            elif n.z < -0.65 and self.vel.z > 0.0:
                # Ceiling.
                self._set_vertical_velocity(0.0, source=MotionWriteSource.COLLISION, reason="slide.ceil_stop")

            clip_n = self._choose_clip_normal(n)
            if self.vel.dot(clip_n) < 0.0:
                self._set_velocity(
                    self._clip_velocity(self.vel, clip_n),
                    source=MotionWriteSource.COLLISION,
                    reason="slide.clip_hit",
                )
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
                    self._set_velocity(
                        self._clip_velocity(self.vel, clip_p),
                        source=MotionWriteSource.COLLISION,
                        reason="slide.clip_multiplane",
                    )

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
        self._set_velocity(
            LVector3f(start_vel),
            source=MotionWriteSource.COLLISION,
            reason="stepslide.reset_second_try",
        )

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
            self._set_velocity(
                LVector3f(vel1),
                source=MotionWriteSource.COLLISION,
                reason="stepslide.choose_plain",
            )
        else:
            self.pos = pos2
            self._set_velocity(
                LVector3f(vel2),
                source=MotionWriteSource.COLLISION,
                reason="stepslide.choose_step",
            )

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
            self._set_vertical_velocity(0.0, source=MotionWriteSource.COLLISION, reason="ground_snap")

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
            self._contact_count += 1

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
                self._set_horizontal_velocity(
                    x=0.0,
                    y=float(self.vel.y),
                    source=MotionWriteSource.COLLISION,
                    reason="axis_resolve_x",
                )
                self._wall_contact_timer = 0.0
            elif axis == "y":
                if delta > 0:
                    self.pos.y = box.minimum.y - self.player_half.y
                    self._wall_normal = LVector3f(0, -1, 0)
                else:
                    self.pos.y = box.maximum.y + self.player_half.y
                    self._wall_normal = LVector3f(0, 1, 0)
                self._set_horizontal_velocity(
                    x=float(self.vel.x),
                    y=0.0,
                    source=MotionWriteSource.COLLISION,
                    reason="axis_resolve_y",
                )
                self._wall_contact_timer = 0.0
            else:
                if delta > 0:
                    self.pos.z = box.minimum.z - self.player_half.z
                else:
                    self.pos.z = box.maximum.z + self.player_half.z
                    self.grounded = True
                self._set_vertical_velocity(0.0, source=MotionWriteSource.COLLISION, reason="axis_resolve_z")

            paabb = self._player_aabb()
