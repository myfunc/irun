from __future__ import annotations

import math


class CameraHeightObserver:
    """Read-only vertical eye-offset smoothing for slide/vault transitions."""

    def __init__(self) -> None:
        self._ready = False
        self._offset_z = 0.0

    def reset(self) -> None:
        self._ready = False

    def observe(
        self,
        *,
        dt: float,
        target_offset_z: float,
        enabled: bool,
        base_hz: float = 12.0,
        boost_hz_per_unit: float = 18.0,
    ) -> float:
        if not bool(enabled):
            self._ready = False
            return float(target_offset_z)

        if not self._ready:
            self._offset_z = float(target_offset_z)
            self._ready = True
            return float(self._offset_z)

        frame_dt = max(0.0, float(dt))
        if frame_dt <= 0.0:
            return float(self._offset_z)

        delta = float(target_offset_z) - float(self._offset_z)
        hz = max(0.0, float(base_hz)) + abs(delta) * max(0.0, float(boost_hz_per_unit))
        alpha = 1.0 - math.exp(-hz * frame_dt) if hz > 0.0 else 1.0
        alpha = max(0.0, min(1.0, alpha))
        self._offset_z += delta * alpha
        return float(self._offset_z)

