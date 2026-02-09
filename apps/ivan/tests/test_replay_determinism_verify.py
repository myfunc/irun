from __future__ import annotations

import json
from pathlib import Path

from ivan.replays.determinism_verify import verify_replay_determinism


def _write_demo(path: Path) -> Path:
    payload = {
        "format_version": 3,
        "metadata": {
            "demo_name": "det",
            "created_at_unix": 1.0,
            "tick_rate": 60,
            "look_scale": 256,
            "map_id": "det-route",
            "map_json": None,
            "tuning": {
                "max_ground_speed": 6.0,
                "run_t90": 0.2,
                "ground_stop_t90": 0.2,
                "jump_height": 1.2,
                "jump_apex_time": 0.3,
                "slide_enabled": True,
                "slide_stop_t90": 3.0,
            },
        },
        "frames": [
            {
                "dx": 0,
                "dy": 0,
                "mf": 1,
                "mr": 0,
                "jp": False,
                "jh": False,
                "sp": True,
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
            },
            {
                "dx": 0,
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
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_verify_replay_determinism_reports_stable_runs(tmp_path: Path) -> None:
    replay = _write_demo(tmp_path / "det.ivan_demo.json")

    result = verify_replay_determinism(
        replay_path=replay,
        runs=3,
        out_dir=tmp_path / "out",
    )

    assert result.runs == 3
    assert result.tick_count == 2
    assert result.stable is True
    assert result.divergence_runs == 0
    assert result.report_path.exists()
