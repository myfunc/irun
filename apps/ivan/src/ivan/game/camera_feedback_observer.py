from __future__ import annotations

import math
from dataclasses import dataclass

from panda3d.core import LVector3f


@dataclass(frozen=True)
class CameraFeedbackPose:
    fov_deg: float
    pitch_deg: float
    roll_deg: float
    speed_ratio: float = 0.0
    speed_t: float = 0.0
    speed_fov_add_deg: float = 0.0
    target_fov_deg: float = 0.0
    event_name: str = "none"
    event_quality: float = 0.0
    event_applied_amp: float = 0.0
    event_blocked_reason: str = "none"


class CameraFeedbackObserver:
    """Read-only camera feedback layer (speed FOV + landing/bhop event pulses)."""

    def __init__(self) -> None:
        self._ready_fov = False
        self._fov_deg = 96.0
        self._event_target = 0.0
        self._event_env = 0.0
        self._last_jump_press_time = -999.0
        self._last_landing_time = -999.0
        self._event_name = "none"
        self._event_quality = 0.0
        self._event_blocked_reason = "none"

    def reset(self) -> None:
        self._ready_fov = False
        self._event_target = 0.0
        self._event_env = 0.0
        self._last_jump_press_time = -999.0
        self._last_landing_time = -999.0
        self._event_name = "none"
        self._event_quality = 0.0
        self._event_blocked_reason = "none"

    def _trigger_event(self, *, name: str, quality: float) -> None:
        q = max(0.0, min(1.0, float(quality)))
        if q <= 0.0:
            return
        self._event_target = max(float(self._event_target), q)
        self._event_name = str(name)
        self._event_quality = q
        self._event_blocked_reason = "none"

    def record_sim_tick(
        self,
        *,
        now: float,
        jump_pressed: bool,
        jump_held: bool,
        autojump_enabled: bool,
        grace_period: float,
        max_ground_speed: float,
        pre_grounded: bool,
        post_grounded: bool,
        pre_vel: LVector3f,
        post_vel: LVector3f,
    ) -> None:
        if bool(jump_pressed) or (bool(autojump_enabled) and bool(jump_held) and bool(pre_grounded)):
            self._last_jump_press_time = float(now)

        landing = (not bool(pre_grounded)) and bool(post_grounded)
        if landing:
            self._last_landing_time = float(now)
            impact_down = max(0.0, -float(pre_vel.z))
            impact_norm = max(0.0, min(1.0, (impact_down - 1.3) / 7.0))
            if impact_norm > 1e-5:
                self._trigger_event(name="landing", quality=impact_norm)
            else:
                self._event_blocked_reason = "landing_soft"

        takeoff = bool(pre_grounded) and (not bool(post_grounded)) and float(post_vel.z) > 0.05
        if not takeoff:
            return
        window_s = max(0.045, min(0.35, float(grace_period) + 0.03))
        input_ok = (float(now) - float(self._last_jump_press_time)) <= window_s
        # Autojump queues should still count as successful timing windows.
        if bool(autojump_enabled) and bool(jump_held):
            input_ok = True
        if not input_ok:
            self._event_blocked_reason = "bhop_timing"
            return

        pre_hspeed = math.sqrt(float(pre_vel.x) ** 2 + float(pre_vel.y) ** 2)
        speed_ok = pre_hspeed >= max(0.75, float(max_ground_speed) * 0.35)
        recent_landing = (float(now) - float(self._last_landing_time)) <= max(0.035, window_s * 1.15)
        if not (speed_ok or recent_landing):
            self._event_blocked_reason = "bhop_speed"
            return
        speed_ratio = pre_hspeed / max(1e-4, float(max_ground_speed))
        speed_quality = max(0.0, min(1.0, (speed_ratio - 0.35) / 1.8))
        timing_age = max(0.0, float(now) - float(self._last_jump_press_time))
        timing_quality = max(0.0, min(1.0, 1.0 - (timing_age / max(1e-4, window_s))))
        landing_bonus = 0.20 if recent_landing else 0.0
        quality = max(0.0, min(1.0, 0.35 + 0.45 * speed_quality + 0.20 * timing_quality + landing_bonus))
        self._trigger_event(name="bhop", quality=quality)

    def observe(
        self,
        *,
        dt: float,
        horizontal_speed: float,
        max_ground_speed: float,
        enabled: bool,
        base_fov_deg: float,
        speed_fov_max_add_deg: float,
        event_gain: float,
        event_attack_ms: float = 55.0,
        event_release_ms: float = 240.0,
    ) -> CameraFeedbackPose:
        base_fov = max(60.0, min(130.0, float(base_fov_deg)))
        if not bool(enabled):
            self._ready_fov = False
            self._event_target = 0.0
            self._event_env = 0.0
            self._event_name = "none"
            self._event_quality = 0.0
            self._event_blocked_reason = "none"
            return CameraFeedbackPose(
                fov_deg=base_fov,
                pitch_deg=0.0,
                roll_deg=0.0,
                speed_ratio=0.0,
                speed_t=0.0,
                speed_fov_add_deg=0.0,
                target_fov_deg=base_fov,
                event_name="none",
                event_quality=0.0,
                event_applied_amp=0.0,
                event_blocked_reason="none",
            )

        frame_dt = max(0.0, float(dt))
        if frame_dt > 0.0:
            release_tau = max(0.02, float(event_release_ms) * 0.001)
            self._event_target *= math.exp(-frame_dt / release_tau)
            if float(self._event_target) >= float(self._event_env):
                attack_tau = max(0.01, float(event_attack_ms) * 0.001)
                alpha = 1.0 - math.exp(-frame_dt / attack_tau)
            else:
                alpha = 1.0 - math.exp(-frame_dt / release_tau)
            alpha = max(0.0, min(1.0, alpha))
            self._event_env += (float(self._event_target) - float(self._event_env)) * alpha
            if self._event_target <= 1e-4 and self._event_env <= 1e-4:
                self._event_name = "none"
                self._event_quality = 0.0

        # Speed FOV policy:
        # - no widening at/below Vmax
        # - widening starts above Vmax
        # - reaches configured max gain by 10x Vmax
        speed_ratio = float(horizontal_speed) / max(1e-4, float(max_ground_speed))
        speed_over_t = 0.0
        if speed_ratio > 1.0:
            raw = max(0.0, min(1.0, (speed_ratio - 1.0) / 9.0))
            # Ease-out curve: stronger response in practical 2x-5x Vmax range,
            # still capped and deterministic at 10x Vmax.
            speed_over_t = 1.0 - (1.0 - raw) * (1.0 - raw)
        speed_fov = max(0.0, float(speed_fov_max_add_deg)) * float(speed_over_t)

        event_gain_clamped = max(0.0, float(event_gain))
        event_amp = event_gain_clamped * max(0.0, float(self._event_env))
        event_fov = 2.2 * float(event_amp)
        target_fov = max(60.0, min(140.0, base_fov + speed_fov + event_fov))
        if not self._ready_fov:
            self._fov_deg = float(target_fov)
            self._ready_fov = True
        elif frame_dt > 0.0:
            fov_alpha = 1.0 - math.exp(-9.0 * frame_dt)
            self._fov_deg += (float(target_fov) - float(self._fov_deg)) * max(0.0, min(1.0, float(fov_alpha)))

        event_pitch = -2.4 * float(event_amp)

        return CameraFeedbackPose(
            fov_deg=float(self._fov_deg),
            pitch_deg=float(event_pitch),
            roll_deg=0.0,
            speed_ratio=float(speed_ratio),
            speed_t=float(speed_over_t),
            speed_fov_add_deg=float(speed_fov),
            target_fov_deg=float(target_fov),
            event_name=str(self._event_name),
            event_quality=float(self._event_quality),
            event_applied_amp=float(event_amp),
            event_blocked_reason=str(self._event_blocked_reason),
        )
