from __future__ import annotations

import os
from pathlib import Path

from panda3d.core import LVector3f

from ivan.course.volumes import CylinderVolume
from ivan.modes.base import ModeContext
from ivan.modes.time_trial import TimeTrialMode
from ivan.physics.tuning import PhysicsTuning
from ivan.state import get_time_trial_course_override, record_time_trial_run


class _UIStub:
    def __init__(self) -> None:
        self.hud_text: str | None = None

    def set_time_trial_hud(self, text: str | None) -> None:
        self.hud_text = text


class _HostStub:
    def __init__(self) -> None:
        self.pos = LVector3f(0.0, 0.0, 0.0)
        self.yaw = 90.0
        self.now_value = 0.0
        self.leaderboard_held = False
        self.respawn_calls = 0
        self.marker_start = None
        self.marker_finish = None

    def request_respawn(self) -> None:
        self.respawn_calls += 1

    def player_pos(self) -> LVector3f:
        return LVector3f(self.pos)

    def player_yaw_deg(self) -> float:
        return float(self.yaw)

    def now(self) -> float:
        return float(self.now_value)

    def race_leaderboard_held(self) -> bool:
        return bool(self.leaderboard_held)

    def set_time_trial_markers(self, *, start, finish) -> None:
        self.marker_start = start
        self.marker_finish = finish


def _with_state_dir(tmp_path: Path) -> str | None:
    prev = os.environ.get("IRUN_IVAN_STATE_DIR")
    state_dir = str(tmp_path / "state")
    os.environ["IRUN_IVAN_STATE_DIR"] = state_dir
    return prev


def _restore_state_dir(prev: str | None) -> None:
    if prev is None:
        os.environ.pop("IRUN_IVAN_STATE_DIR", None)
    else:
        os.environ["IRUN_IVAN_STATE_DIR"] = prev


def test_time_trial_mode_binds_race_hotkeys() -> None:
    mode = TimeTrialMode(config={})
    names = {name for (name, _cb) in mode.bindings().events}
    assert "5" in names
    assert "6" in names
    assert "f5" in names
    assert "f6" in names


def test_time_trial_mode_places_cylinders_on_5_and_6(tmp_path: Path) -> None:
    prev = _with_state_dir(tmp_path)
    try:
        host = _HostStub()
        ui = _UIStub()
        mode = TimeTrialMode(config={})
        ctx = ModeContext(
            map_id="demo_alt",
            bundle_root=None,
            tuning=PhysicsTuning(),
            ui=ui,
            host=host,
        )
        mode.on_enter(ctx=ctx)

        host.pos = LVector3f(1.0, 2.0, 3.0)
        events = dict(mode.bindings().events)
        events["5"]()
        assert isinstance(host.marker_start, CylinderVolume)
        assert host.marker_finish is None

        host.pos = LVector3f(12.0, 8.0, 4.0)
        events["6"]()
        assert isinstance(host.marker_start, CylinderVolume)
        assert isinstance(host.marker_finish, CylinderVolume)

        ov = get_time_trial_course_override(map_id="demo_alt")
        assert isinstance(ov, dict)
        assert isinstance(ov.get("start_circle"), dict)
        assert isinstance(ov.get("finish_circle"), dict)
    finally:
        _restore_state_dir(prev)


def test_time_trial_leaderboard_shows_while_tab_held(tmp_path: Path) -> None:
    prev = _with_state_dir(tmp_path)
    try:
        record_time_trial_run(map_id="demo_alt", seconds=11.25, finished_at=1.0)
        record_time_trial_run(map_id="demo_alt", seconds=9.75, finished_at=2.0)

        host = _HostStub()
        ui = _UIStub()
        mode = TimeTrialMode(
            config={
                "start_circle": {"center": [0.0, 0.0, 1.0], "radius": 2.0, "half_z": 2.0},
                "finish_circle": {"center": [10.0, 0.0, 1.0], "radius": 2.0, "half_z": 2.0},
            }
        )
        ctx = ModeContext(
            map_id="demo_alt",
            bundle_root=None,
            tuning=PhysicsTuning(),
            ui=ui,
            host=host,
        )
        mode.on_enter(ctx=ctx)
        host.leaderboard_held = True

        mode.tick(now=0.0, player_pos=LVector3f(100.0, 100.0, 0.0))
        assert isinstance(ui.hud_text, str)
        assert "BEST TIMES" in ui.hud_text
        assert "1. 9.750" in ui.hud_text
    finally:
        _restore_state_dir(prev)
