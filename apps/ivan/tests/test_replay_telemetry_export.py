from __future__ import annotations

import csv
import json
from pathlib import Path

from ivan.replays.demo import load_replay
from ivan.replays.telemetry import export_replay_telemetry


def _write_demo(path: Path) -> Path:
    payload = {
        "format_version": 3,
        "metadata": {
            "demo_name": "sample",
            "created_at_unix": 1.0,
            "tick_rate": 60,
            "look_scale": 256,
            "map_id": "route-a",
            "map_json": None,
            "tuning": {},
        },
        "frames": [
            {
                "dx": 1,
                "dy": 0,
                "mf": 1,
                "mr": 0,
                "jp": True,
                "jh": True,
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
                "tm": {"hs": 100.0, "sp": 120.0, "grounded": True},
            },
            {
                "dx": 2,
                "dy": -1,
                "mf": 1,
                "mr": 1,
                "jp": False,
                "jh": True,
                "sp": True,
                "gp": True,
                "nt": False,
                "kw": True,
                "ka": False,
                "ks": False,
                "kd": True,
                "au": True,
                "ad": False,
                "al": False,
                "ar": True,
                "m1": True,
                "m2": False,
                "tm": {"hs": 140.0, "sp": 180.0, "grounded": False},
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_export_replay_telemetry_writes_csv_and_summary(tmp_path: Path) -> None:
    replay_path = _write_demo(tmp_path / "sample.ivan_demo.json")

    exported = export_replay_telemetry(
        replay_path=replay_path,
        out_dir=tmp_path / "out",
        route_tag="A",
        comment="first note",
        route_name="A rooftop",
        feedback_text="camera too sharp",
    )

    assert exported.tick_count == 2
    assert exported.telemetry_tick_count == 2
    assert exported.csv_path.exists()
    assert exported.summary_path.exists()

    with exported.csv_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["key_w_held"] == "1"
    assert rows[1]["key_d_held"] == "1"
    assert rows[1]["tm_hs"] == "140.0"

    summary = json.loads(exported.summary_path.read_text(encoding="utf-8"))
    assert summary["ticks"]["total"] == 2
    assert summary["input_counts"]["key_w_held_ticks"] == 2
    assert summary["metrics"]["horizontal_speed_max"] == 140.0
    assert summary["metrics"]["jump_takeoff"]["attempts"] == 1
    assert "tuning" in summary["demo"]
    assert "landing_speed_loss_avg" in summary["metrics"]
    assert "camera_lin_jerk_avg" in summary["metrics"]
    assert summary["export_metadata"]["route_tag"] == "A"
    assert summary["export_metadata"]["route_name"] == "A rooftop"
    assert summary["export_metadata"]["comment"] == "first note"
    assert summary["export_metadata"]["run_note"] == "first note"
    assert summary["export_metadata"]["feedback_text"] == "camera too sharp"
    assert summary["export_metadata"]["source_demo"].endswith("sample.ivan_demo.json")
    assert len(summary["export_history"]) == 1

    exported2 = export_replay_telemetry(
        replay_path=replay_path,
        out_dir=tmp_path / "out",
        route_tag="A",
        comment="second note",
    )
    summary2 = json.loads(exported2.summary_path.read_text(encoding="utf-8"))
    assert len(summary2["export_history"]) == 2
    assert summary2["export_history"][-1]["comment"] == "second note"

    rec = load_replay(replay_path)
    assert rec.frames[1].key_d_held is True
