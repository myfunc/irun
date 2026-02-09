from __future__ import annotations

import math
from dataclasses import dataclass, field

from panda3d.core import LVector3f


def _angle_delta_deg(a: float, b: float) -> float:
    d = float(b) - float(a)
    while d > 180.0:
        d -= 360.0
    while d < -180.0:
        d += 360.0
    return d


@dataclass
class FeelMetrics:
    # Totals.
    jump_inputs_total: int = 0
    takeoffs_total: int = 0
    jump_success_total: int = 0
    landings_total: int = 0
    landing_speed_loss_total: float = 0.0
    ground_flickers_total: int = 0

    # Camera jerk (approx): linear/angle acceleration.
    cam_lin_jerk_sum: float = 0.0
    cam_lin_jerk_max: float = 0.0
    cam_ang_jerk_sum: float = 0.0
    cam_ang_jerk_max: float = 0.0
    cam_jerk_samples: int = 0

    # Rolling one-second window.
    _window_jump_inputs: int = 0
    _window_takeoffs: int = 0
    _window_jump_success: int = 0
    _window_landings: int = 0
    _window_landing_loss: float = 0.0
    _window_ground_flickers: int = 0
    _window_cam_lin_jerk_sum: float = 0.0
    _window_cam_lin_jerk_max: float = 0.0
    _window_cam_ang_jerk_sum: float = 0.0
    _window_cam_ang_jerk_max: float = 0.0
    _window_cam_samples: int = 0

    # State.
    _last_jump_input_time: float = -999.0
    _jump_to_takeoff_window_s: float = 0.20
    _last_ground_switch_time: float = -999.0
    _ground_flicker_window_s: float = 0.12
    _last_camera_pos: LVector3f | None = None
    _last_camera_vel: LVector3f | None = None
    _last_camera_yaw: float | None = None
    _last_camera_pitch: float | None = None
    _last_camera_yaw_rate: float | None = None
    _last_camera_pitch_rate: float | None = None
    _last_publish_time: float = 0.0
    _summary_line: str = field(default="feel | collecting...", init=False)

    def record_tick(
        self,
        *,
        now: float,
        dt: float,
        jump_pressed: bool,
        pre_grounded: bool,
        post_grounded: bool,
        pre_vel: LVector3f,
        post_vel: LVector3f,
    ) -> None:
        if jump_pressed:
            self.jump_inputs_total += 1
            self._window_jump_inputs += 1
            self._last_jump_input_time = float(now)

        # Ground-state flicker (rapid toggles).
        if bool(pre_grounded) != bool(post_grounded):
            if (float(now) - float(self._last_ground_switch_time)) <= float(self._ground_flicker_window_s):
                self.ground_flickers_total += 1
                self._window_ground_flickers += 1
            self._last_ground_switch_time = float(now)

        # Takeoff detection.
        takeoff = bool(pre_grounded) and (not bool(post_grounded)) and float(post_vel.z) > 0.05
        if takeoff:
            self.takeoffs_total += 1
            self._window_takeoffs += 1
            if (float(now) - float(self._last_jump_input_time)) <= float(self._jump_to_takeoff_window_s):
                self.jump_success_total += 1
                self._window_jump_success += 1

        # Landing retention/loss.
        landing = (not bool(pre_grounded)) and bool(post_grounded)
        if landing:
            self.landings_total += 1
            self._window_landings += 1
            pre_h = math.sqrt(float(pre_vel.x) ** 2 + float(pre_vel.y) ** 2)
            post_h = math.sqrt(float(post_vel.x) ** 2 + float(post_vel.y) ** 2)
            loss = max(0.0, pre_h - post_h)
            self.landing_speed_loss_total += float(loss)
            self._window_landing_loss += float(loss)

    def record_camera_sample(self, *, pos: LVector3f, yaw: float, pitch: float, dt: float) -> None:
        dt = max(1e-6, float(dt))
        if self._last_camera_pos is None:
            self._last_camera_pos = LVector3f(pos)
            self._last_camera_yaw = float(yaw)
            self._last_camera_pitch = float(pitch)
            return

        vel = (LVector3f(pos) - self._last_camera_pos) / dt
        yaw_rate = _angle_delta_deg(float(self._last_camera_yaw), float(yaw)) / dt
        pitch_rate = _angle_delta_deg(float(self._last_camera_pitch), float(pitch)) / dt

        if self._last_camera_vel is not None:
            lin_jerk = ((vel - self._last_camera_vel) / dt).length()
            self.cam_lin_jerk_sum += float(lin_jerk)
            self.cam_lin_jerk_max = max(self.cam_lin_jerk_max, float(lin_jerk))
            self._window_cam_lin_jerk_sum += float(lin_jerk)
            self._window_cam_lin_jerk_max = max(self._window_cam_lin_jerk_max, float(lin_jerk))

            if self._last_camera_yaw_rate is not None and self._last_camera_pitch_rate is not None:
                ang_jerk = math.sqrt(
                    ((float(yaw_rate) - float(self._last_camera_yaw_rate)) / dt) ** 2
                    + ((float(pitch_rate) - float(self._last_camera_pitch_rate)) / dt) ** 2
                )
                self.cam_ang_jerk_sum += float(ang_jerk)
                self.cam_ang_jerk_max = max(self.cam_ang_jerk_max, float(ang_jerk))
                self._window_cam_ang_jerk_sum += float(ang_jerk)
                self._window_cam_ang_jerk_max = max(self._window_cam_ang_jerk_max, float(ang_jerk))

            self.cam_jerk_samples += 1
            self._window_cam_samples += 1

        self._last_camera_pos = LVector3f(pos)
        self._last_camera_vel = LVector3f(vel)
        self._last_camera_yaw = float(yaw)
        self._last_camera_pitch = float(pitch)
        self._last_camera_yaw_rate = float(yaw_rate)
        self._last_camera_pitch_rate = float(pitch_rate)

    def update_summary(self, *, now: float) -> str:
        if self._last_publish_time <= 0.0:
            self._last_publish_time = float(now)
            return self._summary_line
        if (float(now) - float(self._last_publish_time)) < 1.0:
            return self._summary_line

        jump_rate = (
            (float(self._window_jump_success) / float(self._window_takeoffs))
            if self._window_takeoffs > 0
            else 0.0
        )
        landing_loss = (
            (float(self._window_landing_loss) / float(self._window_landings))
            if self._window_landings > 0
            else 0.0
        )
        lin_jerk_mean = (
            float(self._window_cam_lin_jerk_sum) / float(self._window_cam_samples)
            if self._window_cam_samples > 0
            else 0.0
        )
        ang_jerk_mean = (
            float(self._window_cam_ang_jerk_sum) / float(self._window_cam_samples)
            if self._window_cam_samples > 0
            else 0.0
        )

        self._summary_line = (
            "feel | "
            f"jump_ok={jump_rate * 100.0:.0f}% ({self._window_jump_success}/{self._window_takeoffs}) "
            f"land_loss={landing_loss:.3f} "
            f"ground_flicker={self._window_ground_flickers} "
            f"cam_lin_j={lin_jerk_mean:.2f}/{self._window_cam_lin_jerk_max:.2f} "
            f"cam_ang_j={ang_jerk_mean:.2f}/{self._window_cam_ang_jerk_max:.2f}"
        )

        self._window_jump_inputs = 0
        self._window_takeoffs = 0
        self._window_jump_success = 0
        self._window_landings = 0
        self._window_landing_loss = 0.0
        self._window_ground_flickers = 0
        self._window_cam_lin_jerk_sum = 0.0
        self._window_cam_lin_jerk_max = 0.0
        self._window_cam_ang_jerk_sum = 0.0
        self._window_cam_ang_jerk_max = 0.0
        self._window_cam_samples = 0
        self._last_publish_time = float(now)
        return self._summary_line
