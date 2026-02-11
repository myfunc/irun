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
    "run_t90": (0.03, 1.2),
    "ground_stop_t90": (0.03, 1.2),
    "air_speed_mult": (0.5, 4.0),
    "air_gain_t90": (0.03, 1.2),
    "wallrun_sink_t90": (0.03, 1.2),
    "wallrun_min_entry_speed_mult": (0.0, 1.5),
    "wallrun_min_approach_dot": (0.0, 0.8),
    "wallrun_min_parallel_dot": (0.0, 1.0),
    "surf_accel": (0.0, 120.0),
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


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    s = str(text or "").lower()
    return any(p in s for p in phrases)


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

    # Intents are strictly driven by feedback text.
    intent_speed_fast = _has_any(text, ("too fast", "feels fast", "speed too high", "too quick"))
    intent_speed_slow = _has_any(text, ("too slow", "sluggish", "speed too low", "cannot gain speed"))
    intent_accel_fast = _has_any(
        text,
        ("acceleration is too fast", "acceleration too fast", "acceleration too snappy", "ramps too hard"),
    )
    intent_accel_slow = _has_any(
        text,
        ("acceleration too slow", "acceleration too weak", "acceleration feels weak", "can't accelerate"),
    )
    intent_smooth = _has_any(
        text,
        ("not smooth", "doesnt feel smooth", "doesn't feel smooth", "jerky", "jitter", "stutter", "rough"),
    )
    intent_landing_harsh = _has_any(
        text,
        ("landing is harsh", "harsh landing", "lose speed on landing", "landing kills speed"),
    )
    intent_air_steer_weak = _has_any(
        text,
        ("can't steer in air", "cant steer in air", "air control too weak", "air steering weak"),
    )
    intent_air_steer_strong = _has_any(
        text,
        ("too much air control", "air control too strong", "air steering too strong", "too floaty"),
    )
    intent_mouse_fast = _has_any(text, ("mouse too fast", "look too fast", "camera too sensitive", "too twitchy"))
    intent_mouse_slow = _has_any(text, ("mouse too slow", "look too slow", "camera too sluggish"))
    intent_wallrun_aggressive = _has_any(
        text,
        (
            "wallrun too aggressive",
            "accidental wallrun",
            "unexpected wallrun",
            "wallrun engages too easily",
            "wallrun triggers too easily",
            "auto wallrun",
        ),
    )
    intent_wallrun_curved_weak = _has_any(
        text,
        (
            "curved wallrun",
            "curve wallrun",
            "wallrun curved",
            "curved wallruns dont work",
            "curved wallruns don't work",
            "cant wallrun curved",
            "can't wallrun curved",
        ),
    )
    intent_wallrun_weak_general = _has_any(
        text,
        (
            "wallrun doesnt work",
            "wallrun doesn't work",
            "cant wallrun",
            "can't wallrun",
            "wallrun not working",
            "wallrun is not engaging",
            "wallrun not engaging",
            "wallrun isn't engaging",
            "wallrun wont engage",
            "wallrun won't engage",
            "fall off the wall",
            "fall of the wall",
            "fall off wall",
            "falling off the wall",
            "slide off the wall",
            "drop off the wall",
        ),
    )
    intent_false_ground_ledge = _has_any(
        text,
        (
            "walk along bottom ledge",
            "walk along bottom ledge of the wallrun",
            "can walk along bottom ledge",
            "no ground",
            "ledge with no ground",
            "ghost ground",
            "ground where there is no floor",
        ),
    )

    if not any(
        (
            intent_speed_fast,
            intent_speed_slow,
            intent_accel_fast,
            intent_accel_slow,
            intent_smooth,
            intent_landing_harsh,
            intent_air_steer_weak,
            intent_air_steer_strong,
            intent_mouse_fast,
            intent_mouse_slow,
            intent_wallrun_aggressive,
            intent_wallrun_curved_weak,
            intent_wallrun_weak_general,
            intent_false_ground_ledge,
        )
    ):
        return []

    if intent_speed_fast:
        set_mul("max_ground_speed", 0.95, "feedback: speed too fast")
        set_mul("air_speed_mult", 0.95, "feedback: speed too fast")
    if intent_speed_slow:
        set_mul("max_ground_speed", 1.05, "feedback: speed too slow")
        set_mul("air_speed_mult", 1.05, "feedback: speed too slow")

    if intent_accel_fast:
        set_mul("run_t90", 1.08, "feedback: acceleration too fast")
        set_mul("air_gain_t90", 1.08, "feedback: acceleration too fast")
        set_mul("surf_accel", 0.93, "feedback: acceleration too fast")
    if intent_accel_slow:
        set_mul("run_t90", 0.93, "feedback: acceleration too weak")
        set_mul("air_gain_t90", 0.93, "feedback: acceleration too weak")

    if intent_smooth:
        set_add("ground_snap_dist", +0.015, "feedback: smoothness")
        set_add("step_height", +0.030, "feedback: smoothness")
        # Optional metric-aware scaling, but only when smoothness intent is present.
        if isinstance(metrics.get("ground_flicker_per_min"), (int, float)) and float(metrics["ground_flicker_per_min"]) >= 45.0:
            set_add("ground_snap_dist", +0.010, "feedback+metric: high ground flicker")
            set_add("step_height", +0.015, "feedback+metric: high ground flicker")
        if isinstance(metrics.get("camera_lin_jerk_avg"), (int, float)) and float(metrics["camera_lin_jerk_avg"]) >= 120.0:
            set_mul("mouse_sensitivity", 0.96, "feedback+metric: high camera jerk")

    if intent_landing_harsh:
        set_mul("ground_stop_t90", 1.07, "feedback: landing speed loss")
        set_mul("air_gain_t90", 0.96, "feedback: landing speed loss")
        if isinstance(metrics.get("landing_speed_loss_avg"), (int, float)) and float(metrics["landing_speed_loss_avg"]) >= 1.0:
            set_mul("ground_stop_t90", 1.05, "feedback+metric: landing loss confirmed")
            set_mul("air_gain_t90", 0.97, "feedback+metric: landing loss confirmed")

    if intent_air_steer_weak:
        set_mul("air_gain_t90", 0.94, "feedback: weak air steering")
    if intent_air_steer_strong:
        set_mul("air_gain_t90", 1.06, "feedback: too much air steering")

    if intent_mouse_fast:
        set_mul("mouse_sensitivity", 0.95, "feedback: look too fast")
    if intent_mouse_slow:
        set_mul("mouse_sensitivity", 1.05, "feedback: look too slow")
    if intent_wallrun_aggressive:
        set_mul("wallrun_min_entry_speed_mult", 1.10, "feedback: reduce accidental wallrun engage")
        set_add("wallrun_min_approach_dot", +0.03, "feedback: require clearer wallrun approach")
        set_add("wallrun_min_parallel_dot", +0.05, "feedback: require stronger along-wall intent")
    if intent_wallrun_curved_weak:
        set_mul("wallrun_sink_t90", 1.04, "feedback: hold wallrun longer on curves")
        set_mul("wallrun_min_entry_speed_mult", 0.93, "feedback: easier curved wallrun entry speed")
        set_add("wallrun_min_approach_dot", -0.02, "feedback: allow shallow approach for curved walls")
        set_add("wallrun_min_parallel_dot", -0.06, "feedback: allow curved wall tangent transitions")
    if intent_wallrun_weak_general:
        set_mul("wallrun_sink_t90", 1.06, "feedback: wallrun sustain feels weak")
        set_mul("wallrun_min_entry_speed_mult", 0.90, "feedback: easier wallrun entry speed")
        set_add("wallrun_min_approach_dot", -0.02, "feedback: easier wallrun approach")
        set_add("wallrun_min_parallel_dot", -0.05, "feedback: easier along-wall carry")
    if intent_false_ground_ledge:
        set_add("ground_snap_dist", -0.010, "feedback: reduce ledge ghost-ground snap")
        set_add("step_height", -0.020, "feedback: reduce low-ledge stickiness")

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
