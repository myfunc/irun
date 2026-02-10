from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ivan.replays.demo import demo_dir, list_replays
from ivan.replays.telemetry import ReplayTelemetryExport, export_replay_telemetry, telemetry_export_dir


@dataclass(frozen=True)
class ReplayTelemetryComparison:
    latest_export: ReplayTelemetryExport
    reference_export: ReplayTelemetryExport
    comparison_path: Path
    improved_count: int
    regressed_count: int
    equal_count: int
    baseline_export: ReplayTelemetryExport | None = None
    baseline_comparison_path: Path | None = None
    history_path: Path | None = None
    history_run_count: int = 0


@dataclass(frozen=True)
class _RouteSummaryRef:
    summary_path: Path
    payload: dict[str, Any]
    exported_at_unix: float
    route_tag: str | None
    route_name: str | None
    run_note: str | None
    feedback_text: str | None


def _clean_route_tag(tag: str | None) -> str | None:
    if not isinstance(tag, str):
        return None
    out = str(tag).strip().upper()
    return out if out else None


def _metric_preferences() -> dict[str, str]:
    return {
        "metrics.jump_takeoff.success_rate": "higher",
        "metrics.horizontal_speed_avg": "higher",
        "metrics.landing_speed_loss_avg": "lower",
        "metrics.ground_flicker_per_min": "lower",
        "metrics.camera_lin_jerk_avg": "lower",
        "metrics.camera_ang_jerk_avg": "lower",
    }


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
    metric_prefs = _metric_preferences()
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
        "route_tag": _clean_route_tag(route_tag),
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


def _load_summary(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _summary_stem(path: Path) -> str:
    name = path.name
    if name.endswith(".summary.json"):
        return name[: -len(".summary.json")]
    return path.stem


def _exported_at_from_payload(path: Path, payload: dict[str, Any]) -> float:
    md = payload.get("export_metadata") if isinstance(payload.get("export_metadata"), dict) else {}
    if isinstance(md.get("exported_at_unix"), (int, float)):
        return float(md["exported_at_unix"])
    try:
        return float(path.stat().st_mtime)
    except Exception:
        return 0.0


def _summary_ref_from_path(path: Path) -> _RouteSummaryRef | None:
    payload = _load_summary(path)
    if payload is None:
        return None
    md = payload.get("export_metadata") if isinstance(payload.get("export_metadata"), dict) else {}
    route_tag = _clean_route_tag(md.get("route_tag") if isinstance(md.get("route_tag"), str) else None)
    route_name = str(md.get("route_name")).strip() if isinstance(md.get("route_name"), str) and str(md.get("route_name")).strip() else None
    run_note = (
        str(md.get("run_note")).strip()
        if isinstance(md.get("run_note"), str) and str(md.get("run_note")).strip()
        else (
            str(md.get("comment")).strip()
            if isinstance(md.get("comment"), str) and str(md.get("comment")).strip()
            else None
        )
    )
    feedback_text = (
        str(md.get("feedback_text")).strip()
        if isinstance(md.get("feedback_text"), str) and str(md.get("feedback_text")).strip()
        else None
    )
    return _RouteSummaryRef(
        summary_path=Path(path).resolve(),
        payload=payload,
        exported_at_unix=_exported_at_from_payload(Path(path), payload),
        route_tag=route_tag,
        route_name=route_name,
        run_note=run_note,
        feedback_text=feedback_text,
    )


def _route_summary_refs(*, out_dir: Path, route_tag: str | None) -> list[_RouteSummaryRef]:
    expected_tag = _clean_route_tag(route_tag)
    refs: list[_RouteSummaryRef] = []
    for p in sorted(Path(out_dir).glob("*.summary.json")):
        ref = _summary_ref_from_path(p)
        if ref is None:
            continue
        if expected_tag and ref.route_tag != expected_tag:
            continue
        refs.append(ref)
    refs.sort(key=lambda r: float(r.exported_at_unix), reverse=True)
    return refs


def _source_demo_from_ref(ref: _RouteSummaryRef) -> Path:
    md = ref.payload.get("export_metadata") if isinstance(ref.payload.get("export_metadata"), dict) else {}
    source = md.get("source_demo")
    if isinstance(source, str) and source.strip():
        return Path(source).expanduser().resolve()
    stem = _summary_stem(ref.summary_path)
    return (demo_dir() / f"{stem}.ivan_demo.json").resolve()


def _export_from_ref(ref: _RouteSummaryRef) -> ReplayTelemetryExport:
    ticks = ref.payload.get("ticks") if isinstance(ref.payload.get("ticks"), dict) else {}
    stem = _summary_stem(ref.summary_path)
    return ReplayTelemetryExport(
        source_demo=_source_demo_from_ref(ref),
        csv_path=(ref.summary_path.parent / f"{stem}.telemetry.csv").resolve(),
        summary_path=ref.summary_path,
        tick_count=int(ticks.get("total") or 0),
        telemetry_tick_count=int(ticks.get("with_telemetry") or 0),
    )


def _preferred_reference(candidates: list[_RouteSummaryRef]) -> _RouteSummaryRef:
    for ref in candidates:
        if ref.feedback_text or ref.run_note:
            return ref
    return candidates[0]


def _history_metric_row(*, values: list[float], pref: str) -> dict[str, float | int]:
    latest = float(values[-1]) if values else 0.0
    prior = [float(v) for v in values[:-1]]
    baseline = float(values[0]) if values else 0.0
    if not prior:
        return {
            "latest": latest,
            "baseline": baseline,
            "best_prior": latest,
            "median_prior": latest,
            "rank": 1,
            "prior_count": 0,
            "better_than_prior": 0,
        }
    if pref == "higher":
        best_prior = max(prior)
        rank = 1 + sum(1 for v in prior if v > latest + 1e-9)
        better = sum(1 for v in prior if latest > v + 1e-9)
    else:
        best_prior = min(prior)
        rank = 1 + sum(1 for v in prior if v < latest - 1e-9)
        better = sum(1 for v in prior if latest < v - 1e-9)
    return {
        "latest": latest,
        "baseline": baseline,
        "best_prior": float(best_prior),
        "median_prior": float(statistics.median(prior)),
        "rank": int(rank),
        "prior_count": int(len(prior)),
        "better_than_prior": int(better),
    }


def _write_route_history_context(
    *,
    latest_ref: _RouteSummaryRef,
    reference_ref: _RouteSummaryRef,
    refs_desc: list[_RouteSummaryRef],
    out_dir: Path,
    route_tag: str,
) -> tuple[Path, int]:
    refs_asc = list(reversed(refs_desc))
    prefs = _metric_preferences()
    metrics: dict[str, dict[str, float | int | str]] = {}
    for key, pref in prefs.items():
        values = [_get_path(ref.payload, key) for ref in refs_asc]
        row = _history_metric_row(values=values, pref=pref)
        row["preferred_direction"] = "higher_is_better" if pref == "higher" else "lower_is_better"
        metrics[key] = row

    latest_stem = _summary_stem(latest_ref.summary_path)
    payload: dict[str, Any] = {
        "format_version": 1,
        "created_at_unix": float(time.time()),
        "route_tag": route_tag,
        "latest_summary": str(latest_ref.summary_path),
        "reference_summary": str(reference_ref.summary_path),
        "baseline_summary": str(refs_asc[0].summary_path),
        "run_count_total": int(len(refs_asc)),
        "history_count": int(max(0, len(refs_asc) - 1)),
        "latest_route_name": latest_ref.route_name,
        "latest_run_note": latest_ref.run_note,
        "latest_feedback_text": latest_ref.feedback_text,
        "runs": [
            {
                "summary": str(ref.summary_path),
                "exported_at_unix": float(ref.exported_at_unix),
                "route_name": ref.route_name,
                "run_note": ref.run_note,
                "feedback_text": ref.feedback_text,
            }
            for ref in refs_asc
        ],
        "metrics": metrics,
    }
    safe_tag = "".join(ch.lower() if ch.isalnum() else "-" for ch in route_tag).strip("-") or "route"
    out_path = (Path(out_dir) / f"{latest_stem}.route-{safe_tag}.history.json").resolve()
    out_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return out_path, int(len(refs_asc))


def compare_latest_route_exports(
    *,
    route_tag: str,
    out_dir: Path | None = None,
    latest_comment: str | None = None,
    latest_summary: Path | None = None,
) -> ReplayTelemetryComparison:
    tag = _clean_route_tag(route_tag)
    if not tag:
        raise ValueError("Route tag is required for route-scoped replay comparison")

    export_dir = Path(out_dir).expanduser().resolve() if out_dir is not None else telemetry_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)

    refs = _route_summary_refs(out_dir=export_dir, route_tag=tag)
    if latest_summary is not None:
        latest_path = Path(latest_summary).expanduser().resolve()
        selected = next((ref for ref in refs if ref.summary_path == latest_path), None)
        if selected is None:
            raise ValueError(f"Latest summary is not exported under route {tag}: {latest_path.name}")
        refs = [selected] + [ref for ref in refs if ref.summary_path != selected.summary_path]

    if len(refs) < 2:
        raise ValueError(f"Need at least 2 exported runs for route {tag} to compare")

    latest_ref = refs[0]
    latest_export = _export_from_ref(latest_ref)
    if isinstance(latest_comment, str) and latest_comment.strip() and latest_export.source_demo.exists():
        latest_export = export_replay_telemetry(
            replay_path=latest_export.source_demo,
            out_dir=export_dir,
            route_tag=tag,
            comment=latest_comment,
            feedback_text=latest_comment,
        )
        latest_ref = _summary_ref_from_path(latest_export.summary_path) or latest_ref
        refs = _route_summary_refs(out_dir=export_dir, route_tag=tag)
        refs = [latest_ref] + [ref for ref in refs if ref.summary_path != latest_ref.summary_path]

    reference_ref = _preferred_reference(refs[1:])
    reference_export = _export_from_ref(reference_ref)

    latest_stem = _summary_stem(latest_export.summary_path)
    ref_stem = _summary_stem(reference_export.summary_path)
    out_path = export_dir / f"{latest_stem}.compare-vs-{ref_stem}.json"
    path, improved, regressed, equal = compare_exported_summaries(
        latest_summary=latest_export.summary_path,
        reference_summary=reference_export.summary_path,
        out_path=out_path,
        route_tag=tag,
    )

    baseline_export: ReplayTelemetryExport | None = None
    baseline_compare_path: Path | None = None
    if len(refs) >= 3:
        baseline_ref = refs[-1]
        if baseline_ref.summary_path not in {latest_export.summary_path, reference_export.summary_path}:
            baseline_export = _export_from_ref(baseline_ref)
            baseline_out = export_dir / f"{latest_stem}.compare-baseline-{_summary_stem(baseline_export.summary_path)}.json"
            baseline_compare_path, _, _, _ = compare_exported_summaries(
                latest_summary=latest_export.summary_path,
                reference_summary=baseline_export.summary_path,
                out_path=baseline_out,
                route_tag=tag,
            )

    history_path, run_count = _write_route_history_context(
        latest_ref=latest_ref,
        reference_ref=reference_ref,
        refs_desc=refs,
        out_dir=export_dir,
        route_tag=tag,
    )

    return ReplayTelemetryComparison(
        latest_export=latest_export,
        reference_export=reference_export,
        comparison_path=path,
        improved_count=int(improved),
        regressed_count=int(regressed),
        equal_count=int(equal),
        baseline_export=baseline_export,
        baseline_comparison_path=baseline_compare_path,
        history_path=history_path,
        history_run_count=int(run_count),
    )


def compare_latest_replays(
    *,
    out_dir: Path | None = None,
    route_tag: str | None = None,
    latest_comment: str | None = None,
) -> ReplayTelemetryComparison:
    tag = _clean_route_tag(route_tag)
    if tag:
        return compare_latest_route_exports(
            route_tag=tag,
            out_dir=out_dir,
            latest_comment=latest_comment,
        )

    replays = list_replays()
    if len(replays) < 2:
        raise ValueError("Need at least 2 replay files to compare latest run")
    export_dir = Path(out_dir).expanduser().resolve() if out_dir is not None else telemetry_export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)

    latest = export_replay_telemetry(
        replay_path=replays[0],
        out_dir=export_dir,
        route_tag=tag,
        comment=latest_comment,
    )
    reference = export_replay_telemetry(replay_path=replays[1], out_dir=export_dir, route_tag=tag)
    latest_stem = latest.source_demo.stem.replace(".ivan_demo", "")
    ref_stem = reference.source_demo.stem.replace(".ivan_demo", "")
    out_path = export_dir / f"{latest_stem}.compare-vs-{ref_stem}.json"
    path, improved, regressed, equal = compare_exported_summaries(
        latest_summary=latest.summary_path,
        reference_summary=reference.summary_path,
        out_path=out_path,
        route_tag=tag,
    )
    return ReplayTelemetryComparison(
        latest_export=latest,
        reference_export=reference,
        comparison_path=path,
        improved_count=int(improved),
        regressed_count=int(regressed),
        equal_count=int(equal),
    )


__all__ = [
    "ReplayTelemetryComparison",
    "compare_exported_summaries",
    "compare_latest_replays",
    "compare_latest_route_exports",
]
