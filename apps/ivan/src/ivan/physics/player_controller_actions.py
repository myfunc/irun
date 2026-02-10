from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.physics.motion.state import MotionWriteSource


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
            self._add_velocity(
                rope * max(0.0, float(self.tuning.grapple_attach_boost)),
                source=MotionWriteSource.IMPULSE,
                reason="grapple.attach_boost",
            )

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
            along = LVector3f(view_h - away * float(view_h.dot(away)))
            if along.lengthSquared() > 1e-12:
                along.normalize()
            else:
                along = LVector3f(-away.y, away.x, 0.0)
                if along.lengthSquared() > 1e-12:
                    along.normalize()
            jump_dir = away * 0.82 + along * 0.28
            if jump_dir.lengthSquared() <= 1e-12:
                jump_dir = LVector3f(away)
            jump_dir.normalize()

            # Wallrun jump should carry a ground-jump-like horizontal distance profile:
            # preserve current speed if already faster, otherwise launch at Vmax.
            cur_hspeed = math.sqrt(float(self.vel.x) * float(self.vel.x) + float(self.vel.y) * float(self.vel.y))
            base_speed = max(cur_hspeed, float(self._motion_solver.ground_target_speed(speed_scale=1.0)))
            boost = jump_dir * base_speed

            # Enforce strong peel-away while preserving overall speed magnitude.
            min_away_speed = base_speed * 0.72
            away_speed = float(boost.dot(away))
            if away_speed < min_away_speed:
                along_vec = LVector3f(boost - away * away_speed)
                along_len = math.sqrt(float(along_vec.x) * float(along_vec.x) + float(along_vec.y) * float(along_vec.y))
                desired_along = math.sqrt(max(0.0, float(base_speed) * float(base_speed) - float(min_away_speed) * float(min_away_speed)))
                if along_len > 1e-9:
                    along_vec *= desired_along / along_len
                else:
                    along_vec = along * desired_along
                boost = away * min_away_speed + along_vec
        else:
            boost = away * wjb + forward * (wjb * 0.45)
        self._set_horizontal_velocity(
            x=float(boost.x),
            y=float(boost.y),
            source=MotionWriteSource.IMPULSE,
            reason="walljump.horizontal",
        )
        up_speed = float(self._jump_up_speed()) if prefer_camera_forward else float(self._jump_up_speed() * 0.95)
        self._set_vertical_velocity(
            up_speed,
            source=MotionWriteSource.IMPULSE,
            reason="walljump.vertical",
        )
        self._wallrun_active = False
        self._wallrun_reacquire_block_timer = 0.10
        self._wall_jump_lock_timer = 0.0
        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._jump_buffer_timer = 0.0
        self._slide_active = False

    def _try_vault(self, *, yaw_deg: float) -> bool:
        if self.collision is None:
            self._set_vault_debug("vault fail: no collision")
            return False
        if self._vault_cooldown_timer < float(self.tuning.vault_cooldown):
            self._set_vault_debug("vault fail: cooldown")
            return False
        if self._wall_normal.lengthSquared() <= 0.01 or self._wall_contact_timer > 0.40:
            self._prime_vault_wall_contact(yaw_deg=yaw_deg)
        hspeed = math.sqrt(float(self.vel.x) * float(self.vel.x) + float(self.vel.y) * float(self.vel.y))
        grace = max(0.06, float(self._motion_solver.coyote_time(horizontal_speed=hspeed)), 0.24)
        if self._wall_contact_timer > grace or self._wall_normal.lengthSquared() <= 0.01:
            self._set_vault_debug("vault fail: no wall/grace")
            return False
        if not self._is_vault_wall_in_front(yaw_deg=yaw_deg):
            self._set_vault_debug("vault fail: not facing wall")
            return False

        edge_z = self._find_vault_edge_height(yaw_deg=yaw_deg)
        if edge_z is None:
            self._set_vault_debug("vault fail: no ledge top")
            return False

        feet_z = self.pos.z - self.player_half.z
        ledge_delta = edge_z - feet_z
        min_vault = max(0.06, float(self.tuning.vault_min_ledge_height))
        # Keep a hard safety cap while allowing 3x larger vault windows than before.
        max_vault = min(float(self.tuning.vault_max_ledge_height), float(self._standing_half_height) * 6.0)
        # In-air vaulting should not be rejected by "stepable" thresholds that are intended
        # for grounded movement where regular step-up already handles low obstacles.
        if self.grounded and ledge_delta < min_vault:
            self._set_vault_debug(f"vault fail: stepable (h={ledge_delta:.2f} min={min_vault:.2f})")
            return False
        if self.grounded and self._is_obstacle_stepable(yaw_deg=yaw_deg, edge_z=float(edge_z)):
            step_h = max(0.0, float(self.tuning.step_height))
            self._set_vault_debug(f"vault fail: stepable (h={ledge_delta:.2f} step={step_h:.2f})")
            return False
        if ledge_delta > max_vault:
            self._set_vault_debug("vault fail: too high")
            return False
        if feet_z >= edge_z - 0.02:
            self._set_vault_debug("vault fail: already above")
            return False

        self._apply_vault(yaw_deg=yaw_deg, edge_z=float(edge_z))
        self._set_vault_debug(f"vault ok: h={ledge_delta:.2f}", hold=0.55)
        return True

    def _prime_vault_wall_contact(self, *, yaw_deg: float) -> None:
        if self.collision is None:
            return
        h_rad = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if forward.lengthSquared() <= 1e-12:
            return
        forward.normalize()
        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))

        probe_dist = max(0.14, float(self.player_half.x) + 0.28)
        z_offsets = (
            -max(0.05, float(self.player_half.z) * 0.12),
            max(0.20, float(self.player_half.z) * 0.22),
        )
        for z_off in z_offsets:
            start = LVector3f(float(self.pos.x), float(self.pos.y), float(self.pos.z + z_off))
            end = LVector3f(start + forward * probe_dist)
            hit = self._bullet_sweep_closest(start, end)
            if not hit.hasHit():
                continue
            n = LVector3f(hit.getHitNormal())
            if n.lengthSquared() > 1e-12:
                n.normalize()
            if abs(float(n.z)) >= max(0.65, walkable_z):
                continue
            hit_pos = start
            if hasattr(hit, "getHitPos"):
                hit_pos = LVector3f(hit.getHitPos())
            if not self._is_valid_wall_contact(point=hit_pos):
                continue
            self._set_wall_contact(LVector3f(float(n.x), float(n.y), 0.0), hit_pos)
            return

    def _is_vault_wall_in_front(self, *, yaw_deg: float) -> bool:
        if self._wall_normal.lengthSquared() <= 1e-12:
            return False
        h_rad = math.radians(float(yaw_deg))
        forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if forward.lengthSquared() <= 1e-12:
            return False
        forward.normalize()
        wall_n = LVector3f(self._wall_normal.x, self._wall_normal.y, 0.0)
        if wall_n.lengthSquared() <= 1e-12:
            return False
        wall_n.normalize()
        # Facing into the wall means forward is opposite wall normal.
        return float(forward.dot(wall_n)) <= -0.20

    def _find_vault_edge_height(self, *, yaw_deg: float) -> float | None:
        if self.collision is None:
            return None
        wall_n = LVector3f(self._wall_normal)
        if wall_n.lengthSquared() <= 1e-12:
            return None
        wall_n.normalize()
        wall_in = LVector3f(-wall_n.x, -wall_n.y, 0.0)
        if wall_in.lengthSquared() > 1e-12:
            wall_in.normalize()
        h_rad = math.radians(float(yaw_deg))
        cam_forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if cam_forward.lengthSquared() > 1e-12:
            cam_forward.normalize()
        approach = wall_in if wall_in.lengthSquared() > 1e-12 else LVector3f(cam_forward)
        if approach.lengthSquared() <= 1e-12:
            approach = LVector3f(wall_in if wall_in.lengthSquared() > 1e-12 else cam_forward)
        if approach.lengthSquared() <= 1e-12:
            return None
        approach.normalize()
        right = LVector3f(approach.y, -approach.x, 0.0)
        if right.lengthSquared() > 1e-12:
            right.normalize()

        feet_z = self.pos.z - self.player_half.z
        scan_top = feet_z + float(self.tuning.vault_max_ledge_height) + 0.35
        scan_bottom = feet_z - 0.25
        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))
        best_z: float | None = None

        # Probe a small fan of columns above/behind the contacted wall face and look for walkable top surfaces.
        # Ray tests are used here (instead of capsule sweep) to avoid side-wall false hits.
        base_xy = LVector3f(float(self._wall_contact_point.x), float(self._wall_contact_point.y), 0.0)
        if base_xy.lengthSquared() <= 1e-12:
            base_xy = LVector3f(float(self.pos.x), float(self.pos.y), 0.0)
        alt_xy = LVector3f(float(self.pos.x), float(self.pos.y), 0.0)
        origins = (base_xy, alt_xy)
        probe_dists = (
            -max(0.06, float(self.player_half.x) * 0.25),
            0.0,
            0.06,
            max(0.12, float(self.player_half.x) * 0.60),
            max(0.22, float(self.player_half.x) * 1.00),
            max(0.38, float(self.player_half.x) * 1.50),
            max(0.58, float(self.player_half.x) * 2.10),
        )
        side_span = max(0.08, float(self.player_half.x) * 0.45)
        side_offsets = (0.0,) if right.lengthSquared() <= 1e-12 else (-side_span, 0.0, side_span)
        for origin in origins:
            for dist in probe_dists:
                for side in side_offsets:
                    probe_xy = LVector3f(origin.x, origin.y, 0.0) + approach * dist + right * side
                    start = LVector3f(probe_xy.x, probe_xy.y, scan_top)
                    end = LVector3f(probe_xy.x, probe_xy.y, scan_bottom)
                    if hasattr(self.collision, "ray_closest"):
                        hit = self.collision.ray_closest(start, end)
                    else:
                        hit = self._bullet_sweep_closest(start, end)
                    if not hit.hasHit():
                        continue

                    n = LVector3f(hit.getHitNormal())
                    if n.lengthSquared() > 1e-12:
                        n.normalize()
                    if n.z <= walkable_z:
                        continue

                    hit_z = self._hit_z(hit=hit, start=start, end=end)
                    # Ignore near-floor hits; keep true ledge tops even when player is already elevated.
                    if hit_z <= (feet_z + 0.03):
                        continue
                    if best_z is None or hit_z > best_z:
                        best_z = float(hit_z)

        return best_z

    def _is_obstacle_stepable(self, *, yaw_deg: float, edge_z: float) -> bool:
        step_h = max(0.0, float(self.tuning.step_height))
        feet_z = float(self.pos.z - self.player_half.z)
        ledge_delta = float(edge_z) - feet_z
        if ledge_delta > (step_h + 0.08):
            return False
        if self.collision is None:
            return ledge_delta <= (step_h + 0.05)

        walkable_z = self._walkable_threshold_z(float(self.tuning.max_ground_slope_deg))
        wall_in = LVector3f(-self._wall_normal.x, -self._wall_normal.y, 0.0)
        if wall_in.lengthSquared() > 1e-12:
            wall_in.normalize()
        h_rad = math.radians(float(yaw_deg))
        cam_forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
        if cam_forward.lengthSquared() > 1e-12:
            cam_forward.normalize()
        approach = wall_in * 0.75 + cam_forward * 0.25
        if approach.lengthSquared() <= 1e-12:
            approach = LVector3f(wall_in if wall_in.lengthSquared() > 1e-12 else cam_forward)
        if approach.lengthSquared() <= 1e-12:
            return ledge_delta <= (step_h + 0.05)
        approach.normalize()
        right = LVector3f(approach.y, -approach.x, 0.0)
        if right.lengthSquared() > 1e-12:
            right.normalize()

        side_span = max(0.0, float(self.player_half.x) * 0.35)
        side_offsets = (0.0,) if right.lengthSquared() <= 1e-12 else (-side_span, 0.0, side_span)
        step_forward = max(0.06, float(self.player_half.x) * 0.95)

        for side in side_offsets:
            base = self.pos + right * side
            up_to = LVector3f(base.x, base.y, base.z + step_h + 0.02)
            hit_up = self._bullet_sweep_closest(base, up_to)
            if hit_up.hasHit() and float(hit_up.getHitFraction()) < 0.995:
                continue

            fwd_to = LVector3f(up_to + approach * step_forward)
            hit_fwd = self._bullet_sweep_closest(up_to, fwd_to)
            if hit_fwd.hasHit() and float(hit_fwd.getHitFraction()) < 0.995:
                continue

            down_end = LVector3f(fwd_to.x, fwd_to.y, fwd_to.z - step_h - 0.40)
            hit_down = self._bullet_sweep_closest(fwd_to, down_end)
            if not hit_down.hasHit():
                continue

            n = LVector3f(hit_down.getHitNormal())
            if n.lengthSquared() > 1e-12:
                n.normalize()
            if n.z <= walkable_z:
                continue

            hit_z = self._hit_z(hit=hit_down, start=fwd_to, end=down_end)
            if float(hit_z) <= (feet_z + step_h + 0.06):
                return True
        return False

    @staticmethod
    def _hit_z(*, hit, start: LVector3f, end: LVector3f) -> float:
        if hasattr(hit, "getHitPos"):
            return float(LVector3f(hit.getHitPos()).z)
        frac = max(0.0, min(1.0, float(hit.getHitFraction())))
        return float((start + (end - start) * frac).z)

    def _apply_vault(self, *, yaw_deg: float, edge_z: float | None = None) -> None:
        pre_hx = float(self.vel.x)
        pre_hy = float(self.vel.y)
        pre_hspeed = math.sqrt(pre_hx * pre_hx + pre_hy * pre_hy)
        h_rad = math.radians(float(yaw_deg))
        cam_forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0)
        if cam_forward.lengthSquared() > 1e-12:
            cam_forward.normalize()
        wall_in = LVector3f(-self._wall_normal.x, -self._wall_normal.y, 0.0)
        if wall_in.lengthSquared() > 1e-12:
            wall_in.normalize()

        forward = LVector3f(cam_forward)
        if wall_in.lengthSquared() > 1e-12:
            blended = wall_in * 0.65 + cam_forward * 0.35
            if blended.lengthSquared() > 1e-12:
                blended.normalize()
                forward = blended
            else:
                forward = LVector3f(wall_in)

        height_boost = max(0.0, float(self.tuning.vault_height_boost))
        vault_up_scale = 0.48 + min(0.35, height_boost * 0.22)
        vault_up = self._jump_up_speed() * float(self.tuning.vault_jump_multiplier) * vault_up_scale
        self._set_vertical_velocity(
            max(float(self.vel.z), float(vault_up)),
            source=MotionWriteSource.IMPULSE,
            reason="vault.vertical",
        )
        self._add_velocity(
            LVector3f(forward.x, forward.y, 0.0) * float(self.tuning.vault_forward_boost),
            source=MotionWriteSource.IMPULSE,
            reason="vault.forward_boost",
        )
        # Queue a short mantle assist so vault clears the edge smoothly instead of teleporting.
        if edge_z is not None:
            pop_z = max(0.04, min(0.30, 0.06 + height_boost * 0.55))
            target_center_z = float(edge_z) + float(self.player_half.z) + 0.02 + pop_z
            dz = max(0.0, target_center_z - float(self.pos.z))
        else:
            dz = max(0.0, min(0.24, float(self.player_half.z) * 0.04 + height_boost * 0.20))
        mantle_forward = LVector3f(forward.x, forward.y, 0.0) * max(0.42, float(self.player_half.x) * 2.45)
        mantle_delta = LVector3f(0.0, 0.0, max(0.0, float(dz))) + LVector3f(mantle_forward)
        self._queue_vault_assist(delta=mantle_delta, duration=0.32, vertical_first=True)

        # Preserve carried horizontal momentum across vault and add only a modest forward gain.
        hspeed = math.sqrt(float(self.vel.x) * float(self.vel.x) + float(self.vel.y) * float(self.vel.y))
        min_gain = min(0.45, max(0.12, float(self.tuning.vault_forward_boost) * 0.35))
        min_post_hspeed = pre_hspeed + min_gain
        if hspeed < min_post_hspeed and hspeed > 1e-9:
            s = min_post_hspeed / hspeed
            self._set_horizontal_velocity(
                x=float(self.vel.x) * s,
                y=float(self.vel.y) * s,
                source=MotionWriteSource.SOLVER,
                reason="vault.hspeed_preserve",
            )
            hspeed = min_post_hspeed
        max_vault_hspeed = max(
            pre_hspeed + max(0.70, float(self.tuning.vault_forward_boost) * 0.95),
            float(self._motion_solver.air_speed(speed_scale=1.0)) * 2.6,
        )
        if hspeed > max_vault_hspeed and hspeed > 1e-9:
            s = max_vault_hspeed / hspeed
            self._set_horizontal_velocity(
                x=float(self.vel.x) * s,
                y=float(self.vel.y) * s,
                source=MotionWriteSource.SOLVER,
                reason="vault.hspeed_soft_cap",
            )

        self._vault_cooldown_timer = 0.0
        self._vault_camera_timer = self._vault_camera_duration()
        self._vault_exit_airborne_pending = True
        self._vault_collision_ignore_timer = 0.12
        self._vault_collision_ignore_normal = LVector3f(self._wall_normal.x, self._wall_normal.y, 0.0)
        if self._vault_collision_ignore_normal.lengthSquared() > 1e-12:
            self._vault_collision_ignore_normal.normalize()
        self._vault_collision_ignore_point = LVector3f(self._wall_contact_point)
        self.grounded = False
        self._wall_contact_timer = 999.0
        self._wall_normal = LVector3f(0, 0, 0)
        self._coyote_timer = 0.0
        self._jump_buffer_timer = 0.0
        self._slide_active = False

    def _safe_translate(self, delta: LVector3f) -> None:
        if delta.lengthSquared() <= 1e-12:
            return
        if self._is_vault_collision_paused():
            self._vault_pause_translate(delta)
            return
        if self.collision is None:
            self.pos += delta
            return
        hit = self._bullet_sweep_closest(self.pos, self.pos + delta)
        if hit.hasHit():
            frac = max(0.0, min(1.0, float(hit.getHitFraction()) - 1e-3))
            self.pos += delta * frac
            return
        self.pos += delta

    def _queue_vault_assist(self, *, delta: LVector3f, duration: float, vertical_first: bool = False) -> None:
        total = LVector3f(delta)
        self._vault_assist_queue = []
        if total.lengthSquared() <= 1e-12:
            self._vault_assist_timer = 0.0
            self._vault_assist_vel = LVector3f(0, 0, 0)
            return
        dur = max(1e-3, float(duration))
        # Apply a tiny immediate nudge for responsiveness, then smooth the rest.
        instant = total * 0.04
        self._safe_translate(instant)
        remain = total - instant
        if remain.lengthSquared() <= 1e-12:
            self._vault_assist_timer = 0.0
            self._vault_assist_vel = LVector3f(0, 0, 0)
            return

        self._vault_collision_pause_timer = max(float(self._vault_collision_pause_timer), dur + 0.06)

        if vertical_first:
            up = LVector3f(0.0, 0.0, max(0.0, float(remain.z)))
            planar = LVector3f(float(remain.x), float(remain.y), min(0.0, float(remain.z)))
            up_len = float(up.length())
            planar_len = float(planar.length())
            if up_len > 1e-6 and planar_len > 1e-6:
                self._vault_assist_queue.append((up, dur * 0.42))
                self._vault_assist_queue.append((planar, dur * 0.58))
            elif up_len > 1e-6:
                self._vault_assist_queue.append((up, dur))
            elif planar_len > 1e-6:
                self._vault_assist_queue.append((planar, dur))
        else:
            self._vault_assist_queue.append((remain, dur))

        self._vault_assist_timer = 0.0
        self._vault_assist_vel = LVector3f(0, 0, 0)
        self._start_next_vault_assist_segment()

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
            self._add_velocity(
                -n * radial_out,
                source=MotionWriteSource.CONSTRAINT,
                reason="grapple.remove_radial_out",
            )
        pull_max = max(0.0, float(self.tuning.grapple_pull_strength))
        pull = min(pull_max, max(0.0, (dist - self._grapple_length) / max(1e-5, dt)))
        self._add_velocity(
            -n * pull,
            source=MotionWriteSource.CONSTRAINT,
            reason="grapple.pull",
        )

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
            self._add_velocity(
                -n * radial_out,
                source=MotionWriteSource.CONSTRAINT,
                reason="grapple.enforce_length",
            )

    def _current_target_half_height(self) -> float:
        stand_h = max(0.15, float(self._standing_half_height))
        if self.crouched:
            target = max(0.30, min(1.0, float(self.tuning.slide_half_height_mult)))
            return min(stand_h, max(0.15, stand_h * target))
        return stand_h

    def _update_slide_hull_state(self, slide_active: bool) -> None:
        target = bool(slide_active)
        if target == self.crouched:
            return
        if target:
            self._apply_slide_hull(True)
            self.crouched = True
            return

        if self._can_uncrouch():
            self._apply_slide_hull(False)
            self.crouched = False

    def _apply_slide_hull(self, crouched: bool) -> None:
        old_half = float(self.player_half.z)
        stand_h = max(0.15, float(self._standing_half_height))
        low_h = min(
            stand_h,
            max(0.15, stand_h * max(0.30, min(1.0, float(self.tuning.slide_half_height_mult)))),
        )
        new_half = low_h if crouched else stand_h
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
