from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ivan.physics.tuning import PhysicsTuning
from ivan.replays.compare import ReplayTelemetryComparison, compare_latest_route_exports
from ivan.replays.telemetry import telemetry_export_dir

from .feel_feedback import TuningAdjustment

_INVARIANT_BOUNDS: dict[str, tuple[float, float]] = {
    "max_ground_speed": (3.0, 40.0),
    "run_t90": (0.03, 1.20),
    "ground_stop_t90": (0.03, 1.20),
    "air_speed_mult": (0.50, 4.00),
    "air_gain_t90": (0.03, 1.20),
    "wallrun_sink_t90": (0.03, 1.20),
    "wallrun_min_entry_speed_mult": (0.0, 1.50),
    "wallrun_min_approach_dot": (0.0, 0.80),
    "wallrun_min_parallel_dot": (0.0, 1.00),
    "jump_height": (0.20, 4.00),
    "jump_apex_time": (0.08, 1.20),
    "grace_period": (0.0, 0.35),
    "slide_stop_t90": (0.10, 8.00),
    "camera_base_fov": (70.0, 125.0),
    "camera_speed_fov_max_add": (0.0, 30.0),
    "camera_tilt_gain": (0.0, 2.5),
    "camera_event_gain": (0.0, 3.0),
}

_TIMING_FIELDS: set[str] = {
    "run_t90",
    "ground_stop_t90",
    "air_gain_t90",
    "wallrun_sink_t90",
    "jump_apex_time",
    "slide_stop_t90",
    "grace_period",
}
_CAMERA_GAIN_FIELDS: set[str] = {"camera_tilt_gain", "camera_event_gain"}
_WALLRUN_GATE_FIELDS: set[str] = {
    "wallrun_min_entry_speed_mult",
    "wallrun_min_approach_dot",
    "wallrun_min_parallel_dot",
}
_ALLOWED_FIELDS: set[str] = set(_INVARIANT_BOUNDS.keys())
_ROUTE_TAGS: set[str] = {"A", "B", "C"}


@dataclass(frozen=True)
class RouteContext:
    route_tag: str
    latest_summary: dict[str, Any] | None
    latest_summary_path: Path | None
    history_payload: dict[str, Any] | None
    history_path: Path | None
    comparison_path: Path | None
    note: str


@dataclass(frozen=True)
class GuardrailCheck:
    name: str
    passed: bool
    latest: float
    reference: float
    detail: str


@dataclass(frozen=True)
class AutotuneEvaluation:
    route_tag: str
    passed: bool
    score: float
    improved_count: int
    regressed_count: int
    equal_count: int
    comparison_path: Path
    history_path: Path | None
    checks: list[GuardrailCheck]


def normalize_route_tag(tag: str | None) -> str:
    out = str(tag or "").strip().upper()
    if out not in _ROUTE_TAGS:
        raise ValueError("Route tag must be one of: A, B, C")
    return out


def _safe_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return float(default)


def _metric(summary: dict[str, Any] | None, path: str, default: float = 0.0) -> float:
    if not isinstance(summary, dict):
        return float(default)
    cur: Any = summary
    for part in str(path).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return float(default)
        cur = cur.get(part)
    return _safe_float(cur, default)


def _has_any(text: str, phrases: tuple[str, ...]) -> bool:
    s = str(text or "").lower()
    return any(p in s for p in phrases)


def _clamp(field: str, value: float) -> float:
    lo, hi = _INVARIANT_BOUNDS[field]
    return max(float(lo), min(float(hi), float(value)))


def _step_limit(field: str, base: float) -> float:
    b = abs(float(base))
    if field in _TIMING_FIELDS:
        return max(0.001, min(0.02, b * 0.08))
    if field in _CAMERA_GAIN_FIELDS:
        return 0.08
    if field in _WALLRUN_GATE_FIELDS:
        return 0.05
    if field == "camera_speed_fov_max_add":
        return max(0.20, b * 0.05)
    if field == "camera_base_fov":
        return max(1.0, b * 0.03)
    return max(0.01, b * 0.05)


def _bounded_target(*, field: str, base: float, raw_target: float) -> float:
    bounded = _clamp(field, float(raw_target))
    lim = _step_limit(field, float(base))
    lo = float(base) - float(lim)
    hi = float(base) + float(lim)
    return max(lo, min(hi, bounded))


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _route_from_summary(summary: dict[str, Any]) -> str | None:
    md = summary.get("export_metadata") if isinstance(summary.get("export_metadata"), dict) else {}
    rt = md.get("route_tag")
    if not isinstance(rt, str):
        return None
    out = str(rt).strip().upper()
    return out if out else None


def _summary_exported_time(path: Path, payload: dict[str, Any]) -> float:
    md = payload.get("export_metadata") if isinstance(payload.get("export_metadata"), dict) else {}
    if isinstance(md.get("exported_at_unix"), (int, float)):
        return float(md["exported_at_unix"])
    try:
        return float(path.stat().st_mtime)
    except Exception:
        return 0.0


def _latest_summary_for_route(*, route_tag: str, out_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    best_path: Path | None = None
    best_payload: dict[str, Any] | None = None
    best_time = -1.0
    for p in sorted(Path(out_dir).glob("*.summary.json")):
        payload = _read_json(p)
        if payload is None:
            continue
        if _route_from_summary(payload) != route_tag:
            continue
        t = _summary_exported_time(p, payload)
        if t > best_time:
            best_time = float(t)
            best_path = Path(p).resolve()
            best_payload = payload
    return best_path, best_payload


def load_route_context(*, route_tag: str, out_dir: Path | None = None) -> RouteContext:
    tag = normalize_route_tag(route_tag)
    export_dir = Path(out_dir).expanduser().resolve() if out_dir is not None else telemetry_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        comp: ReplayTelemetryComparison = compare_latest_route_exports(route_tag=tag, out_dir=export_dir)
        latest_payload = _read_json(comp.latest_export.summary_path)
        history_payload = _read_json(comp.history_path) if comp.history_path is not None else None
        return RouteContext(
            route_tag=tag,
            latest_summary=latest_payload,
            latest_summary_path=Path(comp.latest_export.summary_path).resolve(),
            history_payload=history_payload,
            history_path=(Path(comp.history_path).resolve() if comp.history_path is not None else None),
            comparison_path=Path(comp.comparison_path).resolve(),
            note=f"route compare ready (+{comp.improved_count}/-{comp.regressed_count}/={comp.equal_count})",
        )
    except Exception as e:
        latest_path, latest_payload = _latest_summary_for_route(route_tag=tag, out_dir=export_dir)
        if latest_payload is None:
            return RouteContext(
                route_tag=tag,
                latest_summary=None,
                latest_summary_path=None,
                history_payload=None,
                history_path=None,
                comparison_path=None,
                note=f"no route exports yet ({e})",
            )
        return RouteContext(
            route_tag=tag,
            latest_summary=latest_payload,
            latest_summary_path=latest_path,
            history_payload=None,
            history_path=None,
            comparison_path=None,
            note=f"using latest route summary only ({e})",
        )


def suggest_invariant_adjustments(
    *,
    feedback_text: str,
    tuning: PhysicsTuning,
    latest_summary: dict[str, Any] | None = None,
    history_payload: dict[str, Any] | None = None,
) -> list[TuningAdjustment]:
    text = str(feedback_text or "").strip().lower()
    if not text:
        return []

    metrics = dict(latest_summary.get("metrics") or {}) if isinstance(latest_summary, dict) else {}
    base_vals = {f: float(getattr(tuning, f)) for f in _ALLOWED_FIELDS}
    next_vals = dict(base_vals)
    reasons: dict[str, list[str]] = {f: [] for f in _ALLOWED_FIELDS}

    def set_mul(field: str, mul: float, reason: str) -> None:
        if field not in _ALLOWED_FIELDS:
            return
        raw = float(next_vals[field]) * float(mul)
        next_vals[field] = _bounded_target(field=field, base=base_vals[field], raw_target=raw)
        reasons[field].append(reason)

    def set_add(field: str, add: float, reason: str) -> None:
        if field not in _ALLOWED_FIELDS:
            return
        raw = float(next_vals[field]) + float(add)
        next_vals[field] = _bounded_target(field=field, base=base_vals[field], raw_target=raw)
        reasons[field].append(reason)

    intent_speed_fast = _has_any(text, ("too fast", "speed too high", "too quick", "overspeed"))
    intent_speed_slow = _has_any(text, ("too slow", "sluggish", "speed too low", "cant gain speed", "can't gain speed"))
    intent_accel_fast = _has_any(text, ("accel too fast", "acceleration too fast", "ramps too hard", "too snappy"))
    intent_accel_slow = _has_any(text, ("accel too slow", "acceleration too slow", "acceleration too weak", "can't accelerate"))
    intent_landing_harsh = _has_any(text, ("landing harsh", "lose speed on landing", "landing kills speed", "landing too punishing"))
    intent_jump_low = _has_any(text, ("jump too low", "need more jump", "jump height low", "vault feels low"))
    intent_jump_high = _has_any(text, ("jump too high", "too floaty", "floaty jump", "too much jump"))
    intent_leniency_up = _has_any(text, ("bhop hard", "timing too strict", "miss coyote", "need more grace"))
    intent_leniency_down = _has_any(text, ("too forgiving", "too much grace", "grace too high"))
    intent_wallrun_weak = _has_any(text, ("wallrun too short", "sink too fast", "can't wallrun far"))
    intent_wallrun_strong = _has_any(text, ("wallrun too strong", "wallrun too floaty", "sink too slow"))
    intent_wallrun_aggressive = _has_any(
        text,
        (
            "wallrun too aggressive",
            "wallrun engages too easily",
            "wallrun triggers too easily",
            "accidental wallrun",
            "unexpected wallrun",
        ),
    )
    intent_wallrun_curved = _has_any(
        text,
        (
            "curved wallrun",
            "curve wallrun",
            "wallrun curved",
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
    intent_slide_long = _has_any(text, ("slide too long", "slide keeps speed too much", "slide overpowered"))
    intent_slide_short = _has_any(text, ("slide too short", "slide loses speed too fast", "slide weak"))

    intent_cam_narrow = _has_any(text, ("fov too low", "camera narrow", "need wider fov", "fov too tight"))
    intent_cam_wide = _has_any(text, ("fov too wide", "camera too wide", "need narrower fov"))
    intent_speed_fov_weak = _has_any(text, ("speed fov weak", "need more speed fov", "fov not changing"))
    intent_speed_fov_strong = _has_any(text, ("speed fov too strong", "too much speed fov"))
    intent_tilt_weak = _has_any(text, ("tilt too weak", "need more tilt", "camera not responsive"))
    intent_tilt_strong = _has_any(text, ("tilt too strong", "too much tilt", "camera tilt distracting"))
    intent_cam_harsh = _has_any(text, ("camera harsh", "camera jitter", "camera jerky", "too twitchy"))

    if intent_speed_fast:
        set_mul("max_ground_speed", 0.95, "intent: reduce top speed")
        set_mul("air_speed_mult", 0.95, "intent: reduce air top speed")
    if intent_speed_slow:
        set_mul("max_ground_speed", 1.05, "intent: raise top speed")
        set_mul("air_speed_mult", 1.05, "intent: raise air top speed")

    if intent_accel_fast:
        set_mul("run_t90", 1.08, "intent: soften run acceleration")
        set_mul("air_gain_t90", 1.08, "intent: soften air gain")
    if intent_accel_slow:
        set_mul("run_t90", 0.93, "intent: tighten run acceleration")
        set_mul("air_gain_t90", 0.93, "intent: tighten air gain")

    if intent_landing_harsh:
        set_mul("ground_stop_t90", 1.07, "intent: preserve landing momentum")
        set_mul("air_gain_t90", 0.97, "intent: recover post-landing speed faster")
    if intent_jump_low:
        set_mul("jump_height", 1.04, "intent: increase jump height")
        set_mul("jump_apex_time", 1.03, "intent: keep jump timing natural")
    if intent_jump_high:
        set_mul("jump_height", 0.96, "intent: reduce jump height")
        set_mul("jump_apex_time", 0.96, "intent: reduce floatiness")

    if intent_leniency_up:
        set_mul("grace_period", 1.08, "intent: wider leniency window")
    if intent_leniency_down:
        set_mul("grace_period", 0.92, "intent: tighter leniency window")

    if intent_wallrun_weak:
        set_mul("wallrun_sink_t90", 1.08, "intent: stronger wallrun hold")
        set_mul("wallrun_min_entry_speed_mult", 0.95, "intent: easier wallrun entry speed")
        set_add("wallrun_min_approach_dot", -0.015, "intent: easier wallrun approach")
        set_add("wallrun_min_parallel_dot", -0.03, "intent: easier tangent carry")
    if intent_wallrun_strong:
        set_mul("wallrun_sink_t90", 0.92, "intent: weaker wallrun hold")
        set_mul("wallrun_min_entry_speed_mult", 1.05, "intent: stricter wallrun entry speed")
        set_add("wallrun_min_approach_dot", +0.015, "intent: stricter wallrun approach")
        set_add("wallrun_min_parallel_dot", +0.03, "intent: stricter tangent requirement")
    if intent_wallrun_aggressive:
        set_mul("wallrun_min_entry_speed_mult", 1.08, "intent: reduce accidental wallrun engage")
        set_add("wallrun_min_approach_dot", +0.020, "intent: require clearer wall approach")
        set_add("wallrun_min_parallel_dot", +0.040, "intent: require stronger along-wall travel")
    if intent_wallrun_curved:
        set_mul("wallrun_sink_t90", 1.04, "intent: sustain curved wallrun")
        set_mul("wallrun_min_entry_speed_mult", 0.96, "intent: easier curved wallrun speed gate")
        set_add("wallrun_min_approach_dot", -0.015, "intent: tolerate shallow curved approach")
        set_add("wallrun_min_parallel_dot", -0.040, "intent: tolerate curved tangent shifts")
    if intent_wallrun_weak_general:
        set_mul("wallrun_sink_t90", 1.06, "intent: improve wallrun sustain")
        set_mul("wallrun_min_entry_speed_mult", 0.92, "intent: easier wallrun speed gate")
        set_add("wallrun_min_approach_dot", -0.020, "intent: easier wallrun approach")
        set_add("wallrun_min_parallel_dot", -0.040, "intent: easier wall tangent carry")

    if intent_slide_long:
        set_mul("slide_stop_t90", 0.92, "intent: shorten slide carry")
    if intent_slide_short:
        set_mul("slide_stop_t90", 1.08, "intent: extend slide carry")

    if intent_cam_narrow:
        set_add("camera_base_fov", +2.0, "intent: widen base FOV")
    if intent_cam_wide:
        set_add("camera_base_fov", -2.0, "intent: narrow base FOV")
    if intent_speed_fov_weak:
        set_mul("camera_speed_fov_max_add", 1.06, "intent: stronger speed-FOV")
    if intent_speed_fov_strong:
        set_mul("camera_speed_fov_max_add", 0.94, "intent: softer speed-FOV")
    if intent_tilt_weak:
        set_mul("camera_tilt_gain", 1.08, "intent: stronger camera tilt")
    if intent_tilt_strong:
        set_mul("camera_tilt_gain", 0.92, "intent: weaker camera tilt")
    if intent_cam_harsh:
        set_mul("camera_event_gain", 0.94, "intent: soften camera event pulses")
        set_mul("camera_tilt_gain", 0.96, "intent: reduce camera twitch")

    # Metric-aware reinforcement only when corresponding intent exists.
    if intent_landing_harsh and _safe_float(metrics.get("landing_speed_loss_avg")) >= 1.0:
        set_mul("ground_stop_t90", 1.03, "metric: landing loss confirmed")
    if intent_leniency_up and _metric(latest_summary, "metrics.jump_takeoff.success_rate") <= 0.60:
        set_add("grace_period", +0.01, "metric: jump success is low")
    if intent_cam_harsh and _safe_float(metrics.get("camera_lin_jerk_avg")) >= 120.0:
        set_mul("camera_event_gain", 0.96, "metric: high camera linear jerk")
    if intent_cam_harsh and _safe_float(metrics.get("camera_ang_jerk_avg")) >= 900.0:
        set_mul("camera_tilt_gain", 0.96, "metric: high camera angular jerk")
    if intent_speed_slow:
        rank = _metric(history_payload, "metrics.metrics.horizontal_speed_avg.rank", default=1.0)
        prior_count = _metric(history_payload, "metrics.metrics.horizontal_speed_avg.prior_count", default=0.0)
        if prior_count >= 3.0 and rank > 2.0:
            set_mul("max_ground_speed", 1.03, "metric: speed rank below prior median")

    out: list[TuningAdjustment] = []
    for field in sorted(_ALLOWED_FIELDS):
        before = float(base_vals[field])
        after = float(next_vals[field])
        if abs(after - before) <= 1e-9:
            continue
        why = "; ".join(reasons[field][:3]) if reasons[field] else "autotune"
        out.append(TuningAdjustment(field=field, before=before, after=after, reason=why))
    return out


def _load_summary(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if payload is None:
        raise ValueError(f"Invalid summary payload: {path}")
    return payload


def _score_higher(latest: float, reference: float, scale_floor: float) -> float:
    den = max(float(scale_floor), abs(float(reference)), 1e-6)
    raw = (float(latest) - float(reference)) / den
    return max(-1.0, min(1.0, raw))


def _score_lower(latest: float, reference: float, scale_floor: float) -> float:
    den = max(float(scale_floor), abs(float(reference)), 1e-6)
    raw = (float(reference) - float(latest)) / den
    return max(-1.0, min(1.0, raw))


def _check_min_delta(*, name: str, latest: float, reference: float, min_delta: float, unit: str) -> GuardrailCheck:
    delta = float(latest) - float(reference)
    passed = delta >= float(min_delta)
    detail = f"delta={delta:+.4f}{unit} (min {min_delta:+.4f}{unit})"
    return GuardrailCheck(name=name, passed=bool(passed), latest=float(latest), reference=float(reference), detail=detail)


def _check_max_ratio(
    *,
    name: str,
    latest: float,
    reference: float,
    max_ratio: float,
    fallback_abs_increase: float,
    unit: str,
) -> GuardrailCheck:
    ref = float(reference)
    lat = float(latest)
    if ref > 1e-6:
        limit = ref * float(max_ratio)
    else:
        limit = ref + float(fallback_abs_increase)
    passed = lat <= limit
    detail = f"latest={lat:.4f}{unit} <= limit={limit:.4f}{unit}"
    return GuardrailCheck(name=name, passed=bool(passed), latest=lat, reference=ref, detail=detail)


def evaluate_route_guardrails(*, route_tag: str, out_dir: Path | None = None) -> AutotuneEvaluation:
    tag = normalize_route_tag(route_tag)
    comp = compare_latest_route_exports(route_tag=tag, out_dir=out_dir)
    latest = _load_summary(comp.latest_export.summary_path)
    reference = _load_summary(comp.reference_export.summary_path)

    jump_latest = _metric(latest, "metrics.jump_takeoff.success_rate")
    jump_ref = _metric(reference, "metrics.jump_takeoff.success_rate")
    speed_latest = _metric(latest, "metrics.horizontal_speed_avg")
    speed_ref = _metric(reference, "metrics.horizontal_speed_avg")
    landing_latest = _metric(latest, "metrics.landing_speed_loss_avg")
    landing_ref = _metric(reference, "metrics.landing_speed_loss_avg")
    flicker_latest = _metric(latest, "metrics.ground_flicker_per_min")
    flicker_ref = _metric(reference, "metrics.ground_flicker_per_min")
    cam_lin_latest = _metric(latest, "metrics.camera_lin_jerk_avg")
    cam_lin_ref = _metric(reference, "metrics.camera_lin_jerk_avg")
    cam_ang_latest = _metric(latest, "metrics.camera_ang_jerk_avg")
    cam_ang_ref = _metric(reference, "metrics.camera_ang_jerk_avg")

    checks = [
        _check_min_delta(
            name="jump_success_drop",
            latest=jump_latest,
            reference=jump_ref,
            min_delta=-0.05,
            unit="",
        ),
        _check_max_ratio(
            name="ground_flicker_rise",
            latest=flicker_latest,
            reference=flicker_ref,
            max_ratio=1.15,
            fallback_abs_increase=6.0,
            unit="/min",
        ),
        _check_max_ratio(
            name="camera_lin_jerk_rise",
            latest=cam_lin_latest,
            reference=cam_lin_ref,
            max_ratio=1.20,
            fallback_abs_increase=40.0,
            unit="",
        ),
        _check_max_ratio(
            name="camera_ang_jerk_rise",
            latest=cam_ang_latest,
            reference=cam_ang_ref,
            max_ratio=1.20,
            fallback_abs_increase=250.0,
            unit="",
        ),
        _check_max_ratio(
            name="landing_loss_rise",
            latest=landing_latest,
            reference=landing_ref,
            max_ratio=1.20,
            fallback_abs_increase=0.25,
            unit="",
        ),
    ]
    pass_checks = all(ch.passed for ch in checks)

    components: list[tuple[float, float]] = [
        (3.0, _score_higher(jump_latest, jump_ref, 0.05)),
        (2.0, _score_higher(speed_latest, speed_ref, 1.0)),
        (2.0, _score_lower(landing_latest, landing_ref, 0.2)),
        (1.5, _score_lower(flicker_latest, flicker_ref, 2.0)),
        (1.0, _score_lower(cam_lin_latest, cam_lin_ref, 20.0)),
        (1.0, _score_lower(cam_ang_latest, cam_ang_ref, 120.0)),
    ]
    compare_total = max(1, int(comp.improved_count + comp.regressed_count + comp.equal_count))
    compare_balance = (float(comp.improved_count) - float(comp.regressed_count)) / float(compare_total)
    components.append((1.5, max(-1.0, min(1.0, compare_balance))))
    denom = sum(w for w, _v in components)
    score = float(sum(w * v for w, v in components) / max(1e-6, denom))

    return AutotuneEvaluation(
        route_tag=tag,
        passed=bool(pass_checks and score >= -0.05),
        score=float(score),
        improved_count=int(comp.improved_count),
        regressed_count=int(comp.regressed_count),
        equal_count=int(comp.equal_count),
        comparison_path=Path(comp.comparison_path).resolve(),
        history_path=(Path(comp.history_path).resolve() if comp.history_path is not None else None),
        checks=checks,
    )


__all__ = [
    "AutotuneEvaluation",
    "GuardrailCheck",
    "RouteContext",
    "evaluate_route_guardrails",
    "load_route_context",
    "normalize_route_tag",
    "suggest_invariant_adjustments",
]
