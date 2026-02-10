from __future__ import annotations

import math


class AnimationObserver:
    """Read-only visual observer for lightweight motion-to-camera offsets."""

    def camera_bob_offset_z(
        self,
        *,
        enabled: bool,
        time_s: float,
        horizontal_speed: float,
        reference_speed: float = 6.0,
    ) -> float:
        if not bool(enabled):
            return 0.0
        speed_norm = min(1.0, max(0.0, float(horizontal_speed) / max(1e-6, float(reference_speed))))
        return float(math.sin(float(time_s) * 10.0) * 0.015 * speed_norm)
