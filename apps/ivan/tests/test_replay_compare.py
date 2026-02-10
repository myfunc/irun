from __future__ import annotations

import json
from pathlib import Path

from ivan.replays.telemetry import export_replay_telemetry
from ivan.replays.compare import compare_latest_replays


def _write_demo(path: Path, *, hs_values: list[float], grounded_values: list[bool], jump_pressed_ticks: set[int]) -> Path:
    frames = []
    for i, hs in enumerate(hs_values):
        frames.append(
            {
                "dx": 0,
                "dy": 0,
                "mf": 1,
                "mr": 0,
                "jp": i in jump_pressed_ticks,
                "jh": i in jump_pressed_ticks,
                "sp": False,
                "gp": False,
                "nt": False,
                "kw": True,
                "ka": False,
                "ks": False,
                "kd": False,
                "au": False,
                "ad": False,
                "al": False,
                "ar": False,
                "m1": False,
                "m2": False,
                "tm": {
                    "t": float(i) / 60.0,
                    "x": float(i),
                    "y": 0.0,
                    "z": 0.0,
                    "yaw": 0.0,
                    "pitch": 0.0,
                    "hs": float(hs),
                    "sp": float(hs),
                    "grounded": bool(grounded_values[i]),
                },
            }
        )

    payload = {
        "format_version": 3,
        "metadata": {
            "demo_name": path.stem,
            "created_at_unix": 1.0,
            "tick_rate": 60,
            "look_scale": 256,
            "map_id": "route-a",
            "map_json": None,
            "tuning": {"jump_height": 1.48, "jump_apex_time": 0.351},
        },
        "frames": frames,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_compare_latest_replays_auto_exports_and_writes_comparison(tmp_path: Path, monkeypatch) -> None:
    latest = _write_demo(
        tmp_path / "20260209_010101_latest.ivan_demo.json",
        hs_values=[120.0, 130.0, 135.0],
        grounded_values=[True, False, True],
        jump_pressed_ticks={0},
    )
    reference = _write_demo(
        tmp_path / "20260209_010001_prev.ivan_demo.json",
        hs_values=[90.0, 95.0, 92.0],
        grounded_values=[True, False, True],
        jump_pressed_ticks={0},
    )

    monkeypatch.setattr("ivan.replays.compare.list_replays", lambda: [latest, reference])

    result = compare_latest_replays(out_dir=tmp_path / "out")

    assert result.latest_export.summary_path.exists()
    assert result.reference_export.summary_path.exists()
    assert result.comparison_path.exists()

    payload = json.loads(result.comparison_path.read_text(encoding="utf-8"))
    assert payload["route_tag"] is None
    assert "metrics.horizontal_speed_avg" in payload["metrics"]
    assert payload["result"]["improved_count"] >= 1


def _force_export_time(summary_path: Path, *, exported_at_unix: float) -> None:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    md = payload.get("export_metadata") if isinstance(payload.get("export_metadata"), dict) else {}
    md["exported_at_unix"] = float(exported_at_unix)
    payload["export_metadata"] = md
    summary_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_compare_latest_replays_route_scoped_uses_exported_runs(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    d1 = _write_demo(
        tmp_path / "20260209_010001_a1.ivan_demo.json",
        hs_values=[90.0, 95.0, 92.0],
        grounded_values=[True, False, True],
        jump_pressed_ticks={0},
    )
    d2 = _write_demo(
        tmp_path / "20260209_010101_a2.ivan_demo.json",
        hs_values=[110.0, 120.0, 118.0],
        grounded_values=[True, False, True],
        jump_pressed_ticks={0},
    )
    d3 = _write_demo(
        tmp_path / "20260209_010201_a3.ivan_demo.json",
        hs_values=[130.0, 138.0, 136.0],
        grounded_values=[True, False, True],
        jump_pressed_ticks={0},
    )

    e1 = export_replay_telemetry(replay_path=d1, out_dir=out_dir, route_tag="A")
    _force_export_time(e1.summary_path, exported_at_unix=1.0)
    e2 = export_replay_telemetry(replay_path=d2, out_dir=out_dir, route_tag="A", run_note="too floaty")
    _force_export_time(e2.summary_path, exported_at_unix=2.0)
    e3 = export_replay_telemetry(replay_path=d3, out_dir=out_dir, route_tag="A")
    _force_export_time(e3.summary_path, exported_at_unix=3.0)

    result = compare_latest_replays(out_dir=out_dir, route_tag="A")

    assert result.comparison_path.exists()
    assert result.history_path is not None and result.history_path.exists()
    assert result.history_run_count == 3
    assert result.reference_export.summary_path.name == e2.summary_path.name
    assert result.baseline_export is not None
    assert result.baseline_comparison_path is not None and result.baseline_comparison_path.exists()

    history = json.loads(result.history_path.read_text(encoding="utf-8"))
    assert history["route_tag"] == "A"
    assert history["run_count_total"] == 3
