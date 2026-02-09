from __future__ import annotations

import math
from dataclasses import dataclass

from panda3d.core import LVector3f


@dataclass(frozen=True)
class CameraPose:
    pos: LVector3f
    yaw: float
    pitch: float
    roll: float


class CameraObserver:
    """Read-only camera shell that smooths toward simulation output."""

    def __init__(self) -> None:
        self._ready = False
        self._pos = LVector3f(0, 0, 0)
        self._yaw = 0.0
        self._pitch = 0.0
        self._roll = 0.0

    def reset(self) -> None:
        self._ready = False

    def observe(
        self,
        *,
        target_pos: LVector3f,
        target_yaw: float,
        target_pitch: float,
        dt: float,
        smoothing_enabled: bool,
        smoothing_hz: float,
        target_roll: float = 0.0,
    ) -> CameraPose:
        if not bool(smoothing_enabled):
            self._ready = False
            return CameraPose(pos=LVector3f(target_pos), yaw=float(target_yaw), pitch=float(target_pitch), roll=float(target_roll))

        if not self._ready:
            self._pos = LVector3f(target_pos)
            self._yaw = float(target_yaw)
            self._pitch = float(target_pitch)
            self._roll = float(target_roll)
            self._ready = True
            return CameraPose(pos=LVector3f(self._pos), yaw=float(self._yaw), pitch=float(self._pitch), roll=float(self._roll))

        frame_dt = max(0.0, float(dt))
        blend = 1.0 - math.exp(-max(0.0, float(smoothing_hz)) * frame_dt) if frame_dt > 0.0 else 1.0
        self._pos = self._lerp_vec(self._pos, target_pos, blend)
        self._yaw = self._lerp_angle_deg(self._yaw, float(target_yaw), blend)
        self._pitch = self._lerp_angle_deg(self._pitch, float(target_pitch), blend)
        self._roll = self._lerp_angle_deg(self._roll, float(target_roll), blend)
        return CameraPose(pos=LVector3f(self._pos), yaw=float(self._yaw), pitch=float(self._pitch), roll=float(self._roll))

    @staticmethod
    def _lerp_vec(a: LVector3f, b: LVector3f, t: float) -> LVector3f:
        tt = max(0.0, min(1.0, float(t)))
        return LVector3f(
            float(a.x) + (float(b.x) - float(a.x)) * tt,
            float(a.y) + (float(b.y) - float(a.y)) * tt,
            float(a.z) + (float(b.z) - float(a.z)) * tt,
        )

    @staticmethod
    def _lerp_angle_deg(a: float, b: float, t: float) -> float:
        tt = max(0.0, min(1.0, float(t)))
        d = ((float(b) - float(a) + 180.0) % 360.0) - 180.0
        return float(a) + d * tt
