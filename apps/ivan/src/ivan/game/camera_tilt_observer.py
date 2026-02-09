from __future__ import annotations

import math
from dataclasses import dataclass

from panda3d.core import LVector3f


@dataclass(frozen=True)
class CameraTiltPose:
    roll: float
    pitch: float


def motion_tilt_targets(
    *,
    vel: LVector3f,
    yaw_deg: float,
    reference_speed: float,
    strafe_roll_deg: float = 2.4,
    back_pitch_deg: float = 1.6,
) -> CameraTiltPose:
    horiz = LVector3f(float(vel.x), float(vel.y), 0.0)
    speed = float(horiz.length())
    if speed <= 0.35:
        return CameraTiltPose(roll=0.0, pitch=0.0)

    h_rad = math.radians(float(yaw_deg))
    forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
    right = LVector3f(forward.y, -forward.x, 0.0)
    if forward.lengthSquared() <= 1e-12 or right.lengthSquared() <= 1e-12:
        return CameraTiltPose(roll=0.0, pitch=0.0)

    horiz_dir = LVector3f(horiz)
    horiz_dir.normalize()
    side = max(-1.0, min(1.0, float(right.dot(horiz_dir))))
    forward_dot = max(-1.0, min(1.0, float(forward.dot(horiz_dir))))

    speed_norm = min(1.0, max(0.0, speed / max(0.1, float(reference_speed))))
    roll = float(strafe_roll_deg) * side * speed_norm
    # Backpedal pitch is subtle and one-sided by design.
    pitch = float(back_pitch_deg) * max(0.0, -forward_dot) * speed_norm
    return CameraTiltPose(roll=roll, pitch=pitch)


class CameraTiltObserver:
    """Read-only camera tilt smoothing for responsive-but-stable roll/pitch offsets."""

    def __init__(self) -> None:
        self._ready = False
        self._roll = 0.0
        self._pitch = 0.0

    def reset(self) -> None:
        self._ready = False

    def observe(
        self,
        *,
        dt: float,
        target_roll: float,
        target_pitch: float,
        enabled: bool,
        roll_base_hz: float = 14.0,
        roll_boost_hz_per_deg: float = 2.0,
        pitch_base_hz: float = 11.0,
        pitch_boost_hz_per_deg: float = 1.3,
    ) -> CameraTiltPose:
        if not bool(enabled):
            self._ready = False
            return CameraTiltPose(roll=float(target_roll), pitch=float(target_pitch))

        if not self._ready:
            self._roll = float(target_roll)
            self._pitch = float(target_pitch)
            self._ready = True
            return CameraTiltPose(roll=self._roll, pitch=self._pitch)

        frame_dt = max(0.0, float(dt))
        if frame_dt <= 0.0:
            return CameraTiltPose(roll=self._roll, pitch=self._pitch)

        self._roll = self._smooth_angle(
            current=self._roll,
            target=float(target_roll),
            dt=frame_dt,
            base_hz=float(roll_base_hz),
            boost_hz_per_deg=float(roll_boost_hz_per_deg),
        )
        self._pitch = self._smooth_angle(
            current=self._pitch,
            target=float(target_pitch),
            dt=frame_dt,
            base_hz=float(pitch_base_hz),
            boost_hz_per_deg=float(pitch_boost_hz_per_deg),
        )
        return CameraTiltPose(roll=self._roll, pitch=self._pitch)

    @classmethod
    def _smooth_angle(cls, *, current: float, target: float, dt: float, base_hz: float, boost_hz_per_deg: float) -> float:
        delta = cls._angle_delta_deg(float(current), float(target))
        hz = max(0.0, float(base_hz)) + abs(float(delta)) * max(0.0, float(boost_hz_per_deg))
        alpha = 1.0 - math.exp(-hz * max(0.0, float(dt))) if hz > 0.0 else 1.0
        alpha = max(0.0, min(1.0, alpha))
        return float(current) + float(delta) * alpha

    @staticmethod
    def _angle_delta_deg(from_deg: float, to_deg: float) -> float:
        return ((float(to_deg) - float(from_deg) + 180.0) % 360.0) - 180.0

