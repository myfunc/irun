from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ivan.replays.demo import DemoFrame, DemoRecording, list_replays, load_replay


@dataclass(frozen=True)
class ReplayTelemetryExport:
    source_demo: Path
    csv_path: Path
    summary_path: Path
    tick_count: int
    telemetry_tick_count: int


def telemetry_export_dir() -> Path:
    root = Path(__file__).resolve().parents[3] / "replays" / "telemetry_exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _frame_to_row(*, tick: int, frame: DemoFrame) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tick": int(tick),
        "look_dx": int(frame.look_dx),
        "look_dy": int(frame.look_dy),
        "move_forward": int(frame.move_forward),
        "move_right": int(frame.move_right),
        "jump_pressed": int(bool(frame.jump_pressed)),
        "jump_held": int(bool(frame.jump_held)),
        "slide_pressed": int(bool(frame.slide_pressed)),
        "grapple_pressed": int(bool(frame.grapple_pressed)),
        "noclip_toggle_pressed": int(bool(frame.noclip_toggle_pressed)),
        "key_w_held": int(bool(frame.key_w_held)),
        "key_a_held": int(bool(frame.key_a_held)),
        "key_s_held": int(bool(frame.key_s_held)),
        "key_d_held": int(bool(frame.key_d_held)),
        "arrow_up_held": int(bool(frame.arrow_up_held)),
        "arrow_down_held": int(bool(frame.arrow_down_held)),
        "arrow_left_held": int(bool(frame.arrow_left_held)),
        "arrow_right_held": int(bool(frame.arrow_right_held)),
        "mouse_left_held": int(bool(frame.mouse_left_held)),
        "mouse_right_held": int(bool(frame.mouse_right_held)),
    }
    if isinstance(frame.telemetry, dict):
        for k, v in frame.telemetry.items():
            row[f"tm_{str(k)}"] = v
    return row


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / float(len(values)))


def _angle_delta_deg(a: float, b: float) -> float:
    d = float(b) - float(a)
    while d > 180.0:
        d -= 360.0
    while d < -180.0:
        d += 360.0
    return d


def _compute_jump_success(grounded: list[bool], jump_pressed: list[bool], lookahead: int = 6) -> dict[str, float | int]:
    attempts = 0
    success = 0
    for i, jp in enumerate(jump_pressed):
        if not jp:
            continue
        attempts += 1
        win = grounded[i + 1 : i + 1 + max(1, int(lookahead))]
        if any((not g) for g in win):
            success += 1
    rate = (float(success) / float(attempts)) if attempts > 0 else 0.0
    return {"attempts": int(attempts), "success": int(success), "success_rate": float(rate)}


def _compute_ground_flicker(grounded: list[bool]) -> int:
    if len(grounded) <= 1:
        return 0
    flips = 0
    prev = bool(grounded[0])
    for cur in grounded[1:]:
        if bool(cur) != prev:
            flips += 1
        prev = bool(cur)
    return int(flips)


def _compute_landing_loss(tm_frames: list[dict[str, Any]]) -> dict[str, float | int]:
    losses: list[float] = []
    retentions: list[float] = []
    prev_g: bool | None = None
    prev_hs: float | None = None
    for tm in tm_frames:
        if "grounded" not in tm:
            continue
        cur_g = bool(tm.get("grounded"))
        cur_hs = float(tm.get("hs")) if isinstance(tm.get("hs"), (int, float)) else None
        if prev_g is False and cur_g is True and prev_hs is not None and cur_hs is not None:
            loss = max(0.0, float(prev_hs) - float(cur_hs))
            losses.append(float(loss))
            if float(prev_hs) > 1e-6:
                retentions.append(float(cur_hs) / float(prev_hs))
        prev_g = cur_g
        prev_hs = cur_hs
    return {
        "count": int(len(losses)),
        "loss_avg": float(_mean(losses)),
        "loss_max": float(max(losses) if losses else 0.0),
        "retention_avg": float(_mean(retentions)),
    }


def _compute_camera_jerk(tm_frames: list[dict[str, Any]], *, tick_rate: int) -> dict[str, float | int]:
    last_pos: tuple[float, float, float] | None = None
    last_vel: tuple[float, float, float] | None = None
    last_yaw: float | None = None
    last_pitch: float | None = None
    last_yaw_rate: float | None = None
    last_pitch_rate: float | None = None
    last_t: float | None = None

    lin_samples: list[float] = []
    ang_samples: list[float] = []
    fallback_dt = 1.0 / float(max(1, int(tick_rate)))

    for i, tm in enumerate(tm_frames):
        if not all(isinstance(tm.get(k), (int, float)) for k in ("x", "y", "z", "yaw", "pitch")):
            continue
        x = float(tm["x"])
        y = float(tm["y"])
        z = float(tm["z"])
        yaw = float(tm["yaw"])
        pitch = float(tm["pitch"])

        t_val: float | None = float(tm["t"]) if isinstance(tm.get("t"), (int, float)) else None
        if last_pos is None:
            last_pos = (x, y, z)
            last_yaw = yaw
            last_pitch = pitch
            last_t = t_val
            continue

        dt = fallback_dt
        if t_val is not None and last_t is not None:
            dt = max(1e-6, float(t_val) - float(last_t))

        vel = (
            (x - float(last_pos[0])) / dt,
            (y - float(last_pos[1])) / dt,
            (z - float(last_pos[2])) / dt,
        )
        yaw_rate = _angle_delta_deg(float(last_yaw), float(yaw)) / dt if last_yaw is not None else 0.0
        pitch_rate = _angle_delta_deg(float(last_pitch), float(pitch)) / dt if last_pitch is not None else 0.0

        if last_vel is not None:
            lin_jerk = math.sqrt(
                ((float(vel[0]) - float(last_vel[0])) / dt) ** 2
                + ((float(vel[1]) - float(last_vel[1])) / dt) ** 2
                + ((float(vel[2]) - float(last_vel[2])) / dt) ** 2
            )
            lin_samples.append(float(lin_jerk))

            if last_yaw_rate is not None and last_pitch_rate is not None:
                ang_jerk = math.sqrt(
                    ((float(yaw_rate) - float(last_yaw_rate)) / dt) ** 2
                    + ((float(pitch_rate) - float(last_pitch_rate)) / dt) ** 2
                )
                ang_samples.append(float(ang_jerk))

        last_pos = (x, y, z)
        last_vel = vel
        last_yaw = yaw
        last_pitch = pitch
        last_yaw_rate = yaw_rate
        last_pitch_rate = pitch_rate
        last_t = t_val

    return {
        "samples": int(max(len(lin_samples), len(ang_samples))),
        "lin_avg": float(_mean(lin_samples)),
        "lin_max": float(max(lin_samples) if lin_samples else 0.0),
        "ang_avg": float(_mean(ang_samples)),
        "ang_max": float(max(ang_samples) if ang_samples else 0.0),
    }


def _summary(rec: DemoRecording) -> dict[str, Any]:
    frames = list(rec.frames)
    tm_frames = [dict(f.telemetry) for f in frames if isinstance(f.telemetry, dict)]
    tick_rate = max(1, int(rec.metadata.tick_rate))
    duration_s = float(len(frames)) / float(tick_rate)

    hs_values: list[float] = []
    sp_values: list[float] = []
    grounded_values: list[bool] = []
    jump_pressed_values: list[bool] = []
    for f in frames:
        tm = f.telemetry if isinstance(f.telemetry, dict) else {}
        if isinstance(tm.get("hs"), (int, float)):
            hs_values.append(float(tm["hs"]))
        if isinstance(tm.get("sp"), (int, float)):
            sp_values.append(float(tm["sp"]))
        if "grounded" in tm:
            grounded_values.append(bool(tm.get("grounded")))
        jump_pressed_values.append(bool(f.jump_pressed))

    input_counts = {
        "jump_pressed_ticks": int(sum(1 for f in frames if f.jump_pressed)),
        "jump_held_ticks": int(sum(1 for f in frames if f.jump_held)),
        "slide_pressed_ticks": int(sum(1 for f in frames if f.slide_pressed)),
        "move_forward_pos_ticks": int(sum(1 for f in frames if int(f.move_forward) > 0)),
        "move_forward_neg_ticks": int(sum(1 for f in frames if int(f.move_forward) < 0)),
        "move_right_pos_ticks": int(sum(1 for f in frames if int(f.move_right) > 0)),
        "move_right_neg_ticks": int(sum(1 for f in frames if int(f.move_right) < 0)),
        "key_w_held_ticks": int(sum(1 for f in frames if f.key_w_held)),
        "key_a_held_ticks": int(sum(1 for f in frames if f.key_a_held)),
        "key_s_held_ticks": int(sum(1 for f in frames if f.key_s_held)),
        "key_d_held_ticks": int(sum(1 for f in frames if f.key_d_held)),
        "arrow_up_held_ticks": int(sum(1 for f in frames if f.arrow_up_held)),
        "arrow_down_held_ticks": int(sum(1 for f in frames if f.arrow_down_held)),
        "arrow_left_held_ticks": int(sum(1 for f in frames if f.arrow_left_held)),
        "arrow_right_held_ticks": int(sum(1 for f in frames if f.arrow_right_held)),
        "mouse_left_held_ticks": int(sum(1 for f in frames if f.mouse_left_held)),
        "mouse_right_held_ticks": int(sum(1 for f in frames if f.mouse_right_held)),
    }

    jump_success = _compute_jump_success(grounded_values, jump_pressed_values)
    ground_flicker = _compute_ground_flicker(grounded_values)
    landing_loss = _compute_landing_loss(tm_frames)
    camera_jerk = _compute_camera_jerk(tm_frames, tick_rate=tick_rate)
    det_hashes = [str(tm.get("det_h")) for tm in tm_frames if isinstance(tm.get("det_h"), str) and str(tm.get("det_h")).strip()]
    return {
        "format_version": 1,
        "demo": {
            "name": rec.metadata.demo_name,
            "map_id": rec.metadata.map_id,
            "tick_rate": tick_rate,
            "look_scale": int(rec.metadata.look_scale),
            "source_created_at_unix": float(rec.metadata.created_at_unix),
            "map_json": rec.metadata.map_json,
            "tuning": dict(rec.metadata.tuning),
        },
        "ticks": {
            "total": int(len(frames)),
            "duration_s": float(duration_s),
            "with_telemetry": int(len(tm_frames)),
            "telemetry_coverage": float((len(tm_frames) / float(len(frames))) if frames else 0.0),
        },
        "metrics": {
            "horizontal_speed_avg": float(_mean(hs_values)),
            "horizontal_speed_max": float(max(hs_values) if hs_values else 0.0),
            "speed_avg": float(_mean(sp_values)),
            "speed_max": float(max(sp_values) if sp_values else 0.0),
            "grounded_ratio": float(_mean([1.0 if g else 0.0 for g in grounded_values])),
            "ground_flicker_count": int(ground_flicker),
            "ground_flicker_per_min": float((ground_flicker / max(duration_s, 1e-6)) * 60.0),
            "landing_count": int(landing_loss["count"]),
            "landing_speed_loss_avg": float(landing_loss["loss_avg"]),
            "landing_speed_loss_max": float(landing_loss["loss_max"]),
            "landing_speed_retention_avg": float(landing_loss["retention_avg"]),
            "camera_lin_jerk_avg": float(camera_jerk["lin_avg"]),
            "camera_lin_jerk_max": float(camera_jerk["lin_max"]),
            "camera_ang_jerk_avg": float(camera_jerk["ang_avg"]),
            "camera_ang_jerk_max": float(camera_jerk["ang_max"]),
            "camera_jerk_samples": int(camera_jerk["samples"]),
            "det_hash_samples": int(len(det_hashes)),
            "det_hash_last": str(det_hashes[-1]) if det_hashes else "",
            "jump_takeoff": jump_success,
        },
        "input_counts": input_counts,
    }


def export_replay_telemetry(
    *,
    replay_path: Path,
    out_dir: Path | None = None,
    route_tag: str | None = None,
    comment: str | None = None,
) -> ReplayTelemetryExport:
    src = Path(replay_path).expanduser().resolve()
    rec = load_replay(src)
    export_dir = Path(out_dir).expanduser().resolve() if out_dir is not None else telemetry_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)

    stem = src.name[: -len(".ivan_demo.json")] if src.name.endswith(".ivan_demo.json") else src.stem
    csv_path = export_dir / f"{stem}.telemetry.csv"
    summary_path = export_dir / f"{stem}.summary.json"

    rows = [_frame_to_row(tick=i, frame=f) for i, f in enumerate(rec.frames)]
    tm_keys: list[str] = sorted(
        {
            key
            for row in rows
            for key in row.keys()
            if key.startswith("tm_")
        }
    )
    base_keys = [
        "tick",
        "look_dx",
        "look_dy",
        "move_forward",
        "move_right",
        "jump_pressed",
        "jump_held",
        "slide_pressed",
        "grapple_pressed",
        "noclip_toggle_pressed",
        "key_w_held",
        "key_a_held",
        "key_s_held",
        "key_d_held",
        "arrow_up_held",
        "arrow_down_held",
        "arrow_left_held",
        "arrow_right_held",
        "mouse_left_held",
        "mouse_right_held",
    ]
    fieldnames = base_keys + tm_keys
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    summary = _summary(rec)
    now = float(time.time())
    tag = str(route_tag).strip() if isinstance(route_tag, str) and str(route_tag).strip() else None
    note = str(comment).strip() if isinstance(comment, str) and str(comment).strip() else None
    history: list[dict[str, Any]] = []
    if summary_path.exists():
        try:
            prev = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(prev, dict) and isinstance(prev.get("export_history"), list):
                for row in list(prev.get("export_history") or []):
                    if isinstance(row, dict):
                        history.append(dict(row))
        except Exception:
            history = []
    entry: dict[str, Any] = {"exported_at_unix": now}
    if tag:
        entry["route_tag"] = tag
    if note:
        entry["comment"] = note[:800]
    history.append(entry)
    summary["export_metadata"] = dict(entry)
    summary["export_history"] = history[-200:]
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    return ReplayTelemetryExport(
        source_demo=src,
        csv_path=csv_path,
        summary_path=summary_path,
        tick_count=len(rec.frames),
        telemetry_tick_count=int(sum(1 for f in rec.frames if isinstance(f.telemetry, dict))),
    )


def export_latest_replay_telemetry(
    *,
    out_dir: Path | None = None,
    route_tag: str | None = None,
    comment: str | None = None,
) -> ReplayTelemetryExport:
    replays = list_replays()
    if not replays:
        raise ValueError("No replay files found")
    return export_replay_telemetry(
        replay_path=replays[0],
        out_dir=out_dir,
        route_tag=route_tag,
        comment=comment,
    )
