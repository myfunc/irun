from __future__ import annotations

import os
from pathlib import Path

from ivan.state import (
    IvanState,
    get_time_trial_course_override,
    get_time_trial_leaderboard,
    get_time_trial_pb_seconds,
    load_state,
    record_time_trial_run,
    resolve_map_json,
    save_state,
    set_time_trial_course_override,
    update_state,
)
from ivan.paths import app_root as ivan_app_root


def test_state_roundtrip(tmp_path: Path) -> None:
    prev = os.environ.get("IRUN_IVAN_STATE_DIR")
    os.environ["IRUN_IVAN_STATE_DIR"] = str(tmp_path / "state")
    try:
        assert load_state() == IvanState()
        s = IvanState(last_map_json="imported/halflife/valve/bounce", last_game_root="/x", last_mod="valve")
        save_state(s)
        assert load_state() == s
    finally:
        if prev is None:
            os.environ.pop("IRUN_IVAN_STATE_DIR", None)
        else:
            os.environ["IRUN_IVAN_STATE_DIR"] = prev


def test_resolve_map_json_accepts_assets_alias_if_present() -> None:
    # This uses repo assets. If Bounce is removed, update the fixture and expectation.
    bounce = ivan_app_root() / "assets" / "imported" / "halflife" / "valve" / "bounce" / "map.json"
    p = resolve_map_json("imported/halflife/valve/bounce")
    if bounce.exists():
        assert p is not None
        assert p.resolve() == bounce.resolve()
    else:
        assert p is None


def test_update_state_merges_tuning_overrides(tmp_path: Path) -> None:
    prev = os.environ.get("IRUN_IVAN_STATE_DIR")
    os.environ["IRUN_IVAN_STATE_DIR"] = str(tmp_path / "state")
    try:
        update_state(tuning_overrides={"air_speed_mult": 1.7})
        update_state(tuning_overrides={"surf_enabled": True})
        s = load_state()
        assert s.tuning_overrides["air_speed_mult"] == 1.7
        assert s.tuning_overrides["surf_enabled"] is True
    finally:
        if prev is None:
            os.environ.pop("IRUN_IVAN_STATE_DIR", None)
        else:
            os.environ["IRUN_IVAN_STATE_DIR"] = prev


def test_update_state_persists_audio_volume(tmp_path: Path) -> None:
    prev = os.environ.get("IRUN_IVAN_STATE_DIR")
    os.environ["IRUN_IVAN_STATE_DIR"] = str(tmp_path / "state")
    try:
        update_state(master_volume=0.42, sfx_volume=0.73)
        s = load_state()
        assert abs(float(s.master_volume) - 0.42) < 1e-9
        assert abs(float(s.sfx_volume) - 0.73) < 1e-9
    finally:
        if prev is None:
            os.environ.pop("IRUN_IVAN_STATE_DIR", None)
        else:
            os.environ["IRUN_IVAN_STATE_DIR"] = prev


def test_time_trial_persists_pb_and_last(tmp_path: Path) -> None:
    prev = os.environ.get("IRUN_IVAN_STATE_DIR")
    os.environ["IRUN_IVAN_STATE_DIR"] = str(tmp_path / "state")
    try:
        assert get_time_trial_pb_seconds(map_id="m") is None
        new_pb, last, rank = record_time_trial_run(map_id="m", seconds=12.5, finished_at=1.0)
        assert new_pb == 12.5
        assert last == 12.5
        assert rank == (1, 1)
        assert get_time_trial_pb_seconds(map_id="m") == 12.5

        # Slower run: PB stays.
        new_pb2, last2, rank2 = record_time_trial_run(map_id="m", seconds=20.0, finished_at=2.0)
        assert new_pb2 is None
        assert last2 == 20.0
        assert rank2 == (2, 2)
        assert get_time_trial_pb_seconds(map_id="m") == 12.5

        # Faster run: PB updates.
        new_pb3, last3, rank3 = record_time_trial_run(map_id="m", seconds=11.0, finished_at=3.0)
        assert new_pb3 == 11.0
        assert last3 == 11.0
        assert rank3 == (1, 3)
        assert get_time_trial_pb_seconds(map_id="m") == 11.0
        assert get_time_trial_leaderboard(map_id="m", limit=5) == [11.0, 12.5, 20.0]
    finally:
        if prev is None:
            os.environ.pop("IRUN_IVAN_STATE_DIR", None)
        else:
            os.environ["IRUN_IVAN_STATE_DIR"] = prev


def test_time_trial_course_override_roundtrip(tmp_path: Path) -> None:
    prev = os.environ.get("IRUN_IVAN_STATE_DIR")
    os.environ["IRUN_IVAN_STATE_DIR"] = str(tmp_path / "state")
    try:
        assert get_time_trial_course_override(map_id="m") is None
        set_time_trial_course_override(
            map_id="m",
            course={
                "start_aabb": {"min": [0, 0, 0], "max": [1, 1, 1]},
                "finish_aabb": {"min": [10, 10, 0], "max": [11, 11, 1]},
            },
        )
        ov = get_time_trial_course_override(map_id="m")
        assert isinstance(ov, dict)
        assert ov["start_aabb"]["min"] == [0, 0, 0]
        assert ov["finish_aabb"]["max"] == [11, 11, 1]

        set_time_trial_course_override(map_id="m", course=None)
        assert get_time_trial_course_override(map_id="m") is None
    finally:
        if prev is None:
            os.environ.pop("IRUN_IVAN_STATE_DIR", None)
        else:
            os.environ["IRUN_IVAN_STATE_DIR"] = prev
