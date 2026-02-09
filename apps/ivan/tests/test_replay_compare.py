from __future__ import annotations

import json
from pathlib import Path

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
                "ch": False,
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
            "tuning": {"gravity": 24.0},
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

    result = compare_latest_replays(out_dir=tmp_path / "out", route_tag="A")

    assert result.latest_export.summary_path.exists()
    assert result.reference_export.summary_path.exists()
    assert result.comparison_path.exists()

    payload = json.loads(result.comparison_path.read_text(encoding="utf-8"))
    assert payload["route_tag"] == "A"
    assert "metrics.horizontal_speed_avg" in payload["metrics"]
    assert payload["result"]["improved_count"] >= 1
