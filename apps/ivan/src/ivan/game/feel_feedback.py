from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ivan.physics.tuning import PhysicsTuning


@dataclass(frozen=True)
class TuningAdjustment:
    field: str
    before: float | bool
    after: float | bool
    reason: str


_BOUNDS: dict[str, tuple[float, float]] = {
    "max_ground_speed": (3.0, 40.0),
    "max_air_speed": (3.0, 45.0),
    "ground_accel": (5.0, 140.0),
    "jump_accel": (1.0, 140.0),
    "surf_accel": (0.0, 120.0),
    "air_control": (0.0, 1.0),
    "air_counter_strafe_brake": (0.0, 90.0),
    "friction": (0.0, 25.0),
    "step_height": (0.0, 1.2),
    "ground_snap_dist": (0.0, 0.6),
    "mouse_sensitivity": (0.02, 0.40),
}


def _clamp(field: str, value: float) -> float:
    if field not in _BOUNDS:
        return float(value)
    lo, hi = _BOUNDS[field]
    return max(float(lo), min(float(hi), float(value)))


def _apply_mul(current: float, mul: float, field: str) -> float:
    return _clamp(field, float(current) * float(mul))


def _apply_add(current: float, add: float, field: str) -> float:
    return _clamp(field, float(current) + float(add))


def suggest_adjustments(
    *,
    feedback_text: str,
    tuning: PhysicsTuning,
    latest_summary: dict[str, Any] | None = None,
) -> list[TuningAdjustment]:
    text = str(feedback_text or "").strip().lower()
    if not text:
        return []

    metrics = dict(latest_summary.get("metrics") or {}) if isinstance(latest_summary, dict) else {}
    next_values: dict[str, float] = {}
    reasons: dict[str, str] = {}

    def set_mul(field: str, mul: float, reason: str) -> None:
        cur = float(next_values[field]) if field in next_values else float(getattr(tuning, field))
        next_values[field] = _apply_mul(cur, mul, field)
        reasons[field] = reason

    def set_add(field: str, add: float, reason: str) -> None:
        cur = float(next_values[field]) if field in next_values else float(getattr(tuning, field))
        next_values[field] = _apply_add(cur, add, field)
        reasons[field] = reason

    # Speed perception.
    if "too fast" in text or "feels fast" in text:
        set_mul("max_ground_speed", 0.94, "feedback: too fast")
        set_mul("max_air_speed", 0.94, "feedback: too fast")
    if "too slow" in text or "sluggish" in text:
        set_mul("max_ground_speed", 1.06, "feedback: too slow")
        set_mul("max_air_speed", 1.06, "feedback: too slow")

    # Acceleration feel.
    if "acceleration is too fast" in text or "acceleration too fast" in text:
        set_mul("ground_accel", 0.90, "feedback: acceleration too fast")
        set_mul("jump_accel", 0.92, "feedback: acceleration too fast")
        set_mul("surf_accel", 0.92, "feedback: acceleration too fast")
    if "acceleration too weak" in text or "acceleration too slow" in text:
        set_mul("ground_accel", 1.08, "feedback: acceleration too weak")
        set_mul("jump_accel", 1.06, "feedback: acceleration too weak")

    # Smoothness / jitter.
    if "not smooth" in text or "jitter" in text or "jerky" in text:
        set_add("ground_snap_dist", +0.015, "feedback: smoothness")
        set_add("step_height", +0.030, "feedback: smoothness")
        set_mul("air_counter_strafe_brake", 0.90, "feedback: smoothness")
        set_mul("mouse_sensitivity", 0.97, "feedback: smoothness")

    # Use telemetry when available to bias the adjustment magnitude.
    if isinstance(metrics.get("ground_flicker_per_min"), (int, float)):
        if float(metrics.get("ground_flicker_per_min")) >= 45.0:
            set_add("ground_snap_dist", +0.010, "metric: high ground flicker")
            set_add("step_height", +0.020, "metric: high ground flicker")
    if isinstance(metrics.get("camera_lin_jerk_avg"), (int, float)):
        if float(metrics.get("camera_lin_jerk_avg")) >= 120.0:
            set_mul("mouse_sensitivity", 0.95, "metric: high camera linear jerk")
    if isinstance(metrics.get("landing_speed_loss_avg"), (int, float)):
        if float(metrics.get("landing_speed_loss_avg")) >= 1.0:
            set_mul("friction", 0.94, "metric: high landing speed loss")
            set_mul("air_control", 1.04, "metric: high landing speed loss")

    out: list[TuningAdjustment] = []
    for field in sorted(next_values.keys()):
        before = float(getattr(tuning, field))
        after = float(next_values[field])
        if abs(float(after) - float(before)) <= 1e-9:
            continue
        out.append(TuningAdjustment(field=field, before=before, after=after, reason=str(reasons.get(field, "feedback"))))
    return out


def apply_adjustments(*, tuning: PhysicsTuning, adjustments: list[TuningAdjustment]) -> None:
    for adj in adjustments:
        setattr(tuning, str(adj.field), adj.after)

