from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ivan.replays.demo import list_replays
from ivan.replays.telemetry import ReplayTelemetryExport, export_replay_telemetry, telemetry_export_dir


@dataclass(frozen=True)
class ReplayTelemetryComparison:
    latest_export: ReplayTelemetryExport
    reference_export: ReplayTelemetryExport
    comparison_path: Path
    improved_count: int
    regressed_count: int
    equal_count: int


def _get_path(payload: dict[str, Any], key_path: str) -> float:
    cur: Any = payload
    for part in key_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return 0.0
        cur = cur.get(part)
    if isinstance(cur, (int, float)):
        return float(cur)
    return 0.0


def _metric_rows(*, latest: dict[str, Any], reference: dict[str, Any]) -> tuple[dict[str, dict[str, float | str]], int, int, int]:
    metric_prefs = {
        "metrics.jump_takeoff.success_rate": "higher",
        "metrics.horizontal_speed_avg": "higher",
        "metrics.landing_speed_loss_avg": "lower",
        "metrics.ground_flicker_per_min": "lower",
        "metrics.camera_lin_jerk_avg": "lower",
        "metrics.camera_ang_jerk_avg": "lower",
    }
    rows: dict[str, dict[str, float | str]] = {}
    improved = 0
    regressed = 0
    equal = 0
    for key, pref in metric_prefs.items():
        lv = _get_path(latest, key)
        rv = _get_path(reference, key)
        delta = float(lv - rv)
        if abs(delta) < 1e-9:
            better = "equal"
            equal += 1
        elif pref == "higher":
            better = "latest" if lv > rv else "reference"
            improved += 1 if lv > rv else 0
            regressed += 1 if lv < rv else 0
        else:
            better = "latest" if lv < rv else "reference"
            improved += 1 if lv < rv else 0
            regressed += 1 if lv > rv else 0
        rows[key] = {
            "latest": float(lv),
            "reference": float(rv),
            "delta": float(delta),
            "preferred_direction": "higher_is_better" if pref == "higher" else "lower_is_better",
            "better": better,
        }
    return rows, improved, regressed, equal


def _numeric_tuning_delta(*, latest: dict[str, Any], reference: dict[str, Any]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    lk = latest.get("demo", {}).get("tuning") if isinstance(latest.get("demo"), dict) else {}
    rk = reference.get("demo", {}).get("tuning") if isinstance(reference.get("demo"), dict) else {}
    if not isinstance(lk, dict) or not isinstance(rk, dict):
        return out
    for k in sorted(set(lk.keys()) | set(rk.keys())):
        lv = lk.get(k)
        rv = rk.get(k)
        if isinstance(lv, (int, float)) and isinstance(rv, (int, float)):
            if abs(float(lv) - float(rv)) > 1e-9:
                out[str(k)] = {"latest": float(lv), "reference": float(rv), "delta": float(float(lv) - float(rv))}
    return out


def compare_exported_summaries(
    *,
    latest_summary: Path,
    reference_summary: Path,
    out_path: Path,
    route_tag: str | None = None,
) -> tuple[Path, int, int, int]:
    latest = json.loads(Path(latest_summary).read_text(encoding="utf-8"))
    reference = json.loads(Path(reference_summary).read_text(encoding="utf-8"))
    metric_rows, improved, regressed, equal = _metric_rows(latest=latest, reference=reference)
    payload: dict[str, Any] = {
        "format_version": 1,
        "created_at_unix": float(time.time()),
        "route_tag": str(route_tag).strip() if route_tag else None,
        "latest_summary": str(Path(latest_summary).resolve()),
        "reference_summary": str(Path(reference_summary).resolve()),
        "latest_demo": latest.get("demo"),
        "reference_demo": reference.get("demo"),
        "metrics": metric_rows,
        "tuning_delta": _numeric_tuning_delta(latest=latest, reference=reference),
        "result": {
            "improved_count": int(improved),
            "regressed_count": int(regressed),
            "equal_count": int(equal),
        },
    }
    target = Path(out_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return target, int(improved), int(regressed), int(equal)


def compare_latest_replays(
    *,
    out_dir: Path | None = None,
    route_tag: str | None = None,
) -> ReplayTelemetryComparison:
    replays = list_replays()
    if len(replays) < 2:
        raise ValueError("Need at least 2 replay files to compare latest run")
    export_dir = Path(out_dir).expanduser().resolve() if out_dir is not None else telemetry_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)

    latest = export_replay_telemetry(replay_path=replays[0], out_dir=export_dir)
    reference = export_replay_telemetry(replay_path=replays[1], out_dir=export_dir)
    latest_stem = latest.source_demo.stem.replace(".ivan_demo", "")
    ref_stem = reference.source_demo.stem.replace(".ivan_demo", "")
    out_path = export_dir / f"{latest_stem}.compare-vs-{ref_stem}.json"
    path, improved, regressed, equal = compare_exported_summaries(
        latest_summary=latest.summary_path,
        reference_summary=reference.summary_path,
        out_path=out_path,
        route_tag=route_tag,
    )
    return ReplayTelemetryComparison(
        latest_export=latest,
        reference_export=reference,
        comparison_path=path,
        improved_count=int(improved),
        regressed_count=int(regressed),
        equal_count=int(equal),
    )

