from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

from panda3d.core import LVector3f

from ivan.game.determinism import DeterminismTrace, deterministic_state_hash
from ivan.physics.motion.intent import MotionIntent
from ivan.physics.player_controller import PlayerController
from ivan.physics.tuning import PhysicsTuning
from ivan.replays.demo import DemoRecording, list_replays, load_replay
from ivan.replays.telemetry import telemetry_export_dir


@dataclass(frozen=True)
class ReplayDeterminismReport:
    source_demo: Path
    report_path: Path
    runs: int
    tick_count: int
    stable: bool
    baseline_trace_hash: str
    divergence_runs: int
    recorded_hash_checked: int
    recorded_hash_mismatches: int


@dataclass(frozen=True)
class _RunTrace:
    trace_hash: str
    tick_hashes: list[str]
    recorded_checked: int
    recorded_mismatches: int


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _wish_direction_from_axes(*, yaw_deg: float, move_forward: int, move_right: int) -> LVector3f:
    h_rad = math.radians(float(yaw_deg))
    forward = LVector3f(-math.sin(h_rad), math.cos(h_rad), 0.0)
    right = LVector3f(forward.y, -forward.x, 0.0)

    move = LVector3f(0.0, 0.0, 0.0)
    if int(move_forward) > 0:
        move += forward
    elif int(move_forward) < 0:
        move -= forward
    if int(move_right) > 0:
        move += right
    elif int(move_right) < 0:
        move -= right

    if move.lengthSquared() > 1e-12:
        move.normalize()
    return move


def _tuning_from_metadata(rec: DemoRecording) -> PhysicsTuning:
    tuning = PhysicsTuning()
    snap = dict(rec.metadata.tuning or {})
    fields = set(PhysicsTuning.__annotations__.keys())
    for field, value in snap.items():
        if field not in fields:
            continue
        if isinstance(value, bool):
            setattr(tuning, field, bool(value))
        elif isinstance(value, (int, float)):
            setattr(tuning, field, float(value))
    return tuning


def _initial_state(rec: DemoRecording) -> tuple[LVector3f, float, float, LVector3f, bool]:
    spawn = LVector3f(0.0, 0.0, 3.0)
    yaw = 0.0
    pitch = 0.0
    vel = LVector3f(0.0, 0.0, 0.0)
    grounded = False
    if rec.frames:
        tm = rec.frames[0].telemetry if isinstance(rec.frames[0].telemetry, dict) else {}
        if isinstance(tm.get("x"), (int, float)) and isinstance(tm.get("y"), (int, float)) and isinstance(tm.get("z"), (int, float)):
            spawn = LVector3f(float(tm["x"]), float(tm["y"]), float(tm["z"]))
        if isinstance(tm.get("yaw"), (int, float)):
            yaw = float(tm["yaw"])
        if isinstance(tm.get("pitch"), (int, float)):
            pitch = float(tm["pitch"])
        if isinstance(tm.get("vx"), (int, float)) and isinstance(tm.get("vy"), (int, float)) and isinstance(tm.get("vz"), (int, float)):
            vel = LVector3f(float(tm["vx"]), float(tm["vy"]), float(tm["vz"]))
        if "grounded" in tm:
            grounded = bool(tm.get("grounded"))
    return spawn, yaw, pitch, vel, grounded


def _simulate_replay_trace(*, rec: DemoRecording, run_index: int) -> _RunTrace:
    tuning = _tuning_from_metadata(rec)
    spawn, yaw, pitch, vel, grounded = _initial_state(rec)
    ctrl = PlayerController(
        tuning=tuning,
        spawn_point=spawn,
        aabbs=[],
        collision=None,
    )
    ctrl.pos = LVector3f(spawn)
    ctrl.set_external_velocity(vel=LVector3f(vel), reason="determinism.seed")
    ctrl.grounded = bool(grounded)

    tick_rate = max(1, int(rec.metadata.tick_rate))
    dt = 1.0 / float(tick_rate)
    look_scale = max(1, int(rec.metadata.look_scale))
    trace = DeterminismTrace(tick_rate_hz=tick_rate, seconds=max(2.0, min(30.0, len(rec.frames) / float(tick_rate) + 1.0)))
    hashes: list[str] = []
    checked = 0
    mismatches = 0

    for i, frame in enumerate(rec.frames):
        yaw -= (float(frame.look_dx) / float(look_scale)) * float(tuning.mouse_sensitivity)
        pitch = _clamp(
            pitch - (float(frame.look_dy) / float(look_scale)) * float(tuning.mouse_sensitivity),
            -88.0,
            88.0,
        )
        wish = _wish_direction_from_axes(
            yaw_deg=float(yaw),
            move_forward=int(frame.move_forward),
            move_right=int(frame.move_right),
        )
        jump_requested = bool(frame.jump_pressed)
        if bool(tuning.autojump_enabled) and bool(frame.jump_held) and bool(ctrl.grounded):
            jump_requested = True

        ctrl.step_with_intent(
            dt=dt,
            intent=MotionIntent(
                wish_dir=LVector3f(wish),
                jump_requested=bool(jump_requested),
                slide_requested=bool(frame.slide_pressed),
            ),
            yaw_deg=float(yaw),
            pitch_deg=float(pitch),
        )

        tick_hash = deterministic_state_hash(
            pos=LVector3f(ctrl.pos),
            vel=LVector3f(ctrl.vel),
            yaw_deg=float(yaw),
            pitch_deg=float(pitch),
            grounded=bool(ctrl.grounded),
            state=ctrl.motion_state_name(),
            contact_count=ctrl.contact_count(),
            jump_buffer_left=ctrl.jump_buffer_left(),
            coyote_left=ctrl.coyote_left(),
        )
        trace.record(t=float(i + 1) * dt, tick_hash=tick_hash)
        hashes.append(str(tick_hash))

        tm = frame.telemetry if isinstance(frame.telemetry, dict) else None
        exp_hash = str(tm.get("det_h") or "") if tm else ""
        if exp_hash:
            checked += 1
            if exp_hash != tick_hash:
                mismatches += 1

    _ = run_index
    return _RunTrace(
        trace_hash=str(trace.latest_trace_hash()),
        tick_hashes=hashes,
        recorded_checked=int(checked),
        recorded_mismatches=int(mismatches),
    )


def verify_replay_determinism(
    *,
    replay_path: Path,
    runs: int = 5,
    out_dir: Path | None = None,
) -> ReplayDeterminismReport:
    src = Path(replay_path).expanduser().resolve()
    rec = load_replay(src)
    run_count = max(1, int(runs))
    traces = [_simulate_replay_trace(rec=rec, run_index=i) for i in range(run_count)]

    baseline = traces[0]
    divergence_runs = 0
    for tr in traces[1:]:
        if len(tr.tick_hashes) != len(baseline.tick_hashes) or any(a != b for a, b in zip(tr.tick_hashes, baseline.tick_hashes)):
            divergence_runs += 1

    stable = int(divergence_runs) == 0
    checked = int(sum(int(t.recorded_checked) for t in traces))
    mismatches = int(sum(int(t.recorded_mismatches) for t in traces))

    target_dir = Path(out_dir).expanduser().resolve() if out_dir is not None else telemetry_export_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = src.name[: -len(".ivan_demo.json")] if src.name.endswith(".ivan_demo.json") else src.stem
    report_path = target_dir / f"{stem}.determinism.json"

    payload = {
        "format_version": 1,
        "created_at_unix": float(time.time()),
        "source_demo": str(src),
        "runs": int(run_count),
        "tick_count": int(len(baseline.tick_hashes)),
        "stable": bool(stable),
        "baseline_trace_hash": str(baseline.trace_hash),
        "divergence_runs": int(divergence_runs),
        "recorded_hash_checked": int(checked),
        "recorded_hash_mismatches": int(mismatches),
        "run_trace_hashes": [str(t.trace_hash) for t in traces],
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return ReplayDeterminismReport(
        source_demo=src,
        report_path=report_path,
        runs=int(run_count),
        tick_count=int(len(baseline.tick_hashes)),
        stable=bool(stable),
        baseline_trace_hash=str(baseline.trace_hash),
        divergence_runs=int(divergence_runs),
        recorded_hash_checked=int(checked),
        recorded_hash_mismatches=int(mismatches),
    )


def verify_latest_replay_determinism(*, runs: int = 5, out_dir: Path | None = None) -> ReplayDeterminismReport:
    replays = list_replays()
    if not replays:
        raise ValueError("No replay files found")
    return verify_replay_determinism(replay_path=replays[0], runs=runs, out_dir=out_dir)


__all__ = [
    "ReplayDeterminismReport",
    "verify_latest_replay_determinism",
    "verify_replay_determinism",
]
