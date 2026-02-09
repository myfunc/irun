from __future__ import annotations

import json
from pathlib import Path

from ivan.replays.demo import load_replay


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_replay_accepts_v1_payload(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "legacy.ivan_demo.json",
        {
            "format_version": 1,
            "metadata": {
                "demo_name": "legacy",
                "created_at_unix": 1.0,
                "tick_rate": 60,
                "look_scale": 256,
                "map_id": "m",
                "map_json": None,
                "tuning": {},
            },
            "frames": [{"dx": 1, "dy": -2, "mf": 1, "mr": 0, "jp": True, "jh": True, "ch": False, "gp": False, "nt": False}],
        },
    )
    rec = load_replay(p)
    assert len(rec.frames) == 1
    assert rec.frames[0].look_dx == 1
    assert rec.frames[0].telemetry is None


def test_load_replay_v2_reads_frame_telemetry(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "v2.ivan_demo.json",
        {
            "format_version": 2,
            "metadata": {
                "demo_name": "v2",
                "created_at_unix": 1.0,
                "tick_rate": 60,
                "look_scale": 256,
                "map_id": "m",
                "map_json": None,
                "tuning": {},
            },
            "frames": [
                {
                    "dx": 0,
                    "dy": 0,
                    "mf": 0,
                    "mr": 1,
                    "jp": False,
                    "jh": False,
                    "ch": True,
                    "gp": False,
                    "nt": False,
                    "tm": {"x": 1.0, "y": 2.0, "z": 3.0, "yaw": 90.0, "grounded": True},
                }
            ],
        },
    )
    rec = load_replay(p)
    assert len(rec.frames) == 1
    assert rec.frames[0].crouch_held is True
    assert isinstance(rec.frames[0].telemetry, dict)
    assert rec.frames[0].telemetry["yaw"] == 90.0
    # v2 compatibility: if raw held-state bits are missing, fallback is derived from axes.
    assert rec.frames[0].key_d_held is True
    assert rec.frames[0].key_a_held is False
    assert rec.frames[0].raw_wasd_available is False


def test_load_replay_v3_marks_raw_inputs_available_even_when_all_false(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "v3.ivan_demo.json",
        {
            "format_version": 3,
            "metadata": {
                "demo_name": "v3",
                "created_at_unix": 1.0,
                "tick_rate": 60,
                "look_scale": 256,
                "map_id": "m",
                "map_json": None,
                "tuning": {},
            },
            "frames": [
                {
                    "dx": 0,
                    "dy": 0,
                    "mf": -1,
                    "mr": 0,
                    "jp": False,
                    "jh": False,
                    "ch": False,
                    "gp": False,
                    "nt": False,
                    "kw": False,
                    "ka": False,
                    "ks": False,
                    "kd": False,
                    "au": False,
                    "ad": False,
                    "al": False,
                    "ar": False,
                    "m1": False,
                    "m2": False,
                }
            ],
        },
    )
    rec = load_replay(p)
    assert len(rec.frames) == 1
    assert rec.frames[0].move_forward == -1
    assert rec.frames[0].key_s_held is False
    assert rec.frames[0].raw_wasd_available is True
