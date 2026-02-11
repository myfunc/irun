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

    def _is_walkable_ground_normal(self, normal: LVector3f, *, walkable_z: float) -> bool:
        n = LVector3f(normal)
        if n.lengthSquared() <= 1e-12:
            return False
        n.normalize()
        if self._is_surf_normal(n):
            return False
        return float(n.z) > float(walkable_z)

    def _is_ground_contact_point_valid(self, *, hit, start_pos: LVector3f) -> bool:
        if not hasattr(hit, "getHitPos"):
            return True
        try:
            p = LVector3f(hit.getHitPos())
        except Exception:
            return True
        dx = float(p.x - start_pos.x)
        dy = float(p.y - start_pos.y)
        # A downward ground probe should not classify far side-of-capsule hits as floor.
        max_xy = max(0.10, float(self.player_half.x) * 0.62)
        if (dx * dx + dy * dy) > (max_xy * max_xy):
            return False
        drop = float(start_pos.z - p.z)
        if drop < -1e-4:
            return False
        # Reject near-level side grazes (common on ledge/wall seams) while preserving
        # center-foot contacts that keep grounded state stable.
        min_drop = max(0.0, min(0.03, float(self.tuning.step_height) * 0.08))
        if drop < min_drop:
            center_xy = max(0.04, float(self.player_half.x) * 0.22)
            if (dx * dx + dy * dy) > (center_xy * center_xy):
                return False
        # Require support to remain within a conservative center-foot disk; this blocks
        # false grounded states on decorative wall base ledges outside true foot support.
        cdx = float(p.x - self.pos.x)
        cdy = float(p.y - self.pos.y)
        support_r = max(0.08, float(self.player_half.x) * 0.52)
        if (cdx * cdx + cdy * cdy) > (support_r * support_r):
            return False
        return True

    def _ground_probe_offsets(self) -> tuple[LVector3f, ...]:
        r = max(0.02, float(self.player_half.x) * 0.48)
        d = r * 0.72
        return (
            LVector3f(0.0, 0.0, 0.0),
            LVector3f(r, 0.0, 0.0),
            LVector3f(-r, 0.0, 0.0),
            LVector3f(0.0, r, 0.0),
            LVector3f(0.0, -r, 0.0),
            LVector3f(d, d, 0.0),
            LVector3f(d, -d, 0.0),
            LVector3f(-d, d, 0.0),
            LVector3f(-d, -d, 0.0),
        )

    def _ground_probe_lift_distance(self) -> float:
        # Lifted re-probe avoids immediate step-face hits while preserving original depth budget.
        step_h = max(0.0, float(self.tuning.step_height))
        return max(0.02, min(0.16, step_h * 0.33))

    def _find_walkable_ground_contact(
        self,
        *,
        down: LVector3f,
        walkable_z: float,
    ) -> tuple[LVector3f, float] | None:
        if self.collision is None:
            return None
        best_normal: LVector3f | None = None
        best_drop: float | None = None
        base_drop_limit = max(1e-6, abs(float(down.z)))
        for lift in (0.0, float(self._ground_probe_lift_distance())):
            query_down = LVector3f(float(down.x), float(down.y), float(down.z) - float(lift))
            query_len = abs(float(query_down.z))
            if query_len <= 1e-8:
                continue
            for off in self._ground_probe_offsets():
                start = LVector3f(self.pos + off)
                if lift > 0.0:
                    start.z += float(lift)
                hit = self._bullet_sweep_closest(start, start + query_down)
                if not hit.hasHit():
                    continue
                n = LVector3f(hit.getHitNormal())
                if n.lengthSquared() > 1e-12:
                    n.normalize()
                if not self._is_walkable_ground_normal(n, walkable_z=walkable_z):
                    continue
                if not self._is_ground_contact_point_valid(hit=hit, start_pos=start):
                    continue
                frac = max(0.0, min(1.0, float(hit.getHitFraction())))
                drop = max(0.0, float(query_len) * float(frac) - float(lift))
                if drop > (base_drop_limit + 1e-5):
                    continue
                if best_drop is None or drop < best_drop:
                    best_drop = float(drop)
                    best_normal = LVector3f(n)
        if best_normal is None or best_drop is None:
            return None
        return (LVector3f(best_normal), float(best_drop))

    def _walkable_ground_threshold(self) -> float:
        threshold = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))
        # Add mild hysteresis when already grounded/sliding to reduce one-tick floor flicker
        # on noisy slope contacts.
        if self.grounded or self.is_sliding() or bool(getattr(self, "_slide_held", False)):
            return max(0.05, float(threshold) - 0.035)
        return float(threshold)

    def _ground_probe_distance(self, *, for_snap: bool) -> float:
        base = max(0.0 if for_snap else 0.06, float(self.tuning.ground_snap_dist))
        step_h = max(0.0, float(self.tuning.step_height))
        grounded_motion = bool(self.grounded) or self.is_sliding() or bool(getattr(self, "_slide_held", False))
        if for_snap:
            # Quake-style descending step glue: while grounded-style motion is active, allow
            # snapping down up to step height so stair descent stays planted.
            if grounded_motion:
                return max(float(base), min(0.70, float(step_h) + float(base)))
            return max(float(base), min(0.45, float(step_h) * 0.50 + float(base)))
        if grounded_motion:
            return max(float(base), min(0.70, max(float(base), float(step_h) * 0.75)))
        return max(float(base), min(0.45, max(float(base), float(step_h) * 0.45)))

    @staticmethod
    def _clip_velocity(vel: LVector3f, normal: LVector3f, overbounce: float = 1.0) -> LVector3f:
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
        walkable_z = self._walkable_ground_threshold()
        down = LVector3f(0, 0, -float(self._ground_probe_distance(for_snap=False)))
        hit = self._bullet_sweep_closest(self.pos, self.pos + down)
        if not hit.hasHit():
            alt = self._find_walkable_ground_contact(down=down, walkable_z=walkable_z)
            if alt is None:
                self.grounded = False
                return
            self._ground_normal = LVector3f(alt[0])
            self.grounded = True
            return

        n = LVector3f(hit.getHitNormal())
        if n.lengthSquared() > 1e-12:
            n.normalize()
        if self._is_walkable_ground_normal(n, walkable_z=walkable_z) and self._is_ground_contact_point_valid(
            hit=hit, start_pos=self.pos
        ):
            self._ground_normal = n
            self.grounded = True
            return
        surf_contact = self._is_surf_normal(n)
        if surf_contact:
            self._set_surf_contact(n)
        alt = self._find_walkable_ground_contact(down=down, walkable_z=walkable_z)
        if alt is not None:
            self._ground_normal = LVector3f(alt[0])
            self.grounded = True
            return
        if surf_contact:
            self.grounded = False
            return
        self._ground_normal = n
        self.grounded = False

    def _bullet_slide_move(self, delta: LVector3f) -> None:
        # Iterative slide move (Quake-style): sweep -> move -> clip velocity -> repeat.
        if delta.lengthSquared() <= 1e-12:
            return

        pos = LVector3f(self.pos)
        remaining = LVector3f(delta)
        planes: list[LVector3f] = []

        walkable_z = self._walkable_ground_threshold()
        skin = 0.006

        for _ in range(4):
            if remaining.lengthSquared() <= 1e-10:
                break

            sweep_from = LVector3f(pos)
            move = LVector3f(remaining)
            target = pos + move
            hit = self._bullet_sweep_closest(sweep_from, target)
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
            elif n.z > walkable_z and self._is_ground_contact_point_valid(hit=hit, start_pos=sweep_from):
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
        start_grounded = bool(self.grounded)

        # First attempt: plain slide.
        self._bullet_slide_move(delta)
        pos1 = LVector3f(self.pos)
        vel1 = LVector3f(self.vel)
        grounded1 = bool(self.grounded)

        # Second attempt: step up, move horizontally, then step down.
        self.pos = LVector3f(start_pos)
        self._set_velocity(
            LVector3f(start_vel),
            source=MotionWriteSource.COLLISION,
            reason="stepslide.reset_second_try",
        )
        self.grounded = bool(start_grounded)

        step_up = LVector3f(0, 0, float(self.tuning.step_height))
        hit_up = self._bullet_sweep_closest(self.pos, self.pos + step_up)
        if hit_up.hasHit():
            up_frac = max(0.0, min(1.0, float(hit_up.getHitFraction()) - 1e-4))
            self.pos += step_up * up_frac
        else:
            self.pos += step_up
        if float(self.pos.z - start_pos.z) > 1e-6:
            horiz = LVector3f(float(delta.x), float(delta.y), 0.0)
            self._bullet_slide_move(horiz)

            step_down = LVector3f(0, 0, -float(self.tuning.step_height) - 0.01)
            hit_down = self._bullet_sweep_closest(self.pos, self.pos + step_down)
            if hit_down.hasHit():
                frac = max(0.0, float(hit_down.getHitFraction()) - 1e-4)
                self.pos = self.pos + step_down * frac

        pos2 = LVector3f(self.pos)
        vel2 = LVector3f(self.vel)
        grounded2 = bool(self.grounded)

        d1 = (pos1 - start_pos)
        d2 = (pos2 - start_pos)
        dist1 = d1.x * d1.x + d1.y * d1.y
        dist2 = d2.x * d2.x + d2.y * d2.y
        choose_plain = True
        intent = LVector3f(float(delta.x), float(delta.y), 0.0)
        if intent.lengthSquared() > 1e-12:
            intent.normalize()
            p1 = float(d1.dot(intent))
            p2 = float(d2.dot(intent))
            eps = 1e-6
            if p2 > (p1 + eps):
                choose_plain = False
            elif p1 > (p2 + eps):
                choose_plain = True
            elif dist2 > (dist1 + eps):
                choose_plain = False
            elif dist1 > (dist2 + eps):
                choose_plain = True
            else:
                choose_plain = not (grounded2 and not grounded1)
        elif dist2 > dist1:
            choose_plain = False

        if choose_plain:
            self.pos = pos1
            self._set_velocity(
                LVector3f(vel1),
                source=MotionWriteSource.COLLISION,
                reason="stepslide.choose_plain",
            )
            self.grounded = bool(grounded1)
        else:
            self.pos = pos2
            self._set_velocity(
                LVector3f(vel2),
                source=MotionWriteSource.COLLISION,
                reason="stepslide.choose_step",
            )
            self.grounded = bool(grounded2)

    def _bullet_ground_snap(self) -> None:
        # Keep the player glued to ground on small descents (Quake-style ground snap).
        if self.vel.z > 0.0:
            return

        walkable_z = self._walkable_ground_threshold()
        down_dist = float(self._ground_probe_distance(for_snap=True))
        if down_dist <= 0.0:
            return
        down = LVector3f(0, 0, -down_dist)
        hit = self._bullet_sweep_closest(self.pos, self.pos + down)
        chosen_normal: LVector3f | None = None
        chosen_drop: float | None = None
        if hit.hasHit():
            n = LVector3f(hit.getHitNormal())
            if n.lengthSquared() > 1e-12:
                n.normalize()
            if self._is_walkable_ground_normal(n, walkable_z=walkable_z) and self._is_ground_contact_point_valid(
                hit=hit, start_pos=self.pos
            ):
                chosen_normal = LVector3f(n)
                frac = max(0.0, min(1.0, float(hit.getHitFraction())))
                chosen_drop = max(0.0, float(down_dist) * float(frac))
        if chosen_normal is None or chosen_drop is None:
            alt = self._find_walkable_ground_contact(down=down, walkable_z=walkable_z)
            if alt is not None:
                chosen_normal, chosen_drop = alt
        if chosen_normal is None or chosen_drop is None:
            return

        move_drop = max(0.0, min(float(down_dist), float(chosen_drop)) - 1e-4)
        frac = float(move_drop) / max(1e-6, float(down_dist))
        self.pos = self.pos + down * frac
        self.grounded = True
        self._ground_normal = LVector3f(chosen_normal)
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
