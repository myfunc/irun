from __future__ import annotations

import time
import json
from pathlib import Path

from panda3d.core import LVector3f

from ivan.course.time_trial import CourseSpec, TimeTrial, make_marker_aabb
from ivan.course.volumes import aabb_from_json, aabb_to_json
from ivan.maps.bundle_io import run_json_path_for_bundle_ref
from ivan.modes.base import GameMode, ModeBindings, ModeContext, SpawnSpec
from ivan.state import (
    get_time_trial_course_override,
    get_time_trial_pb_seconds,
    record_time_trial_run,
    set_time_trial_course_override,
)


class TimeTrialMode(GameMode):
    id = "time_trial"

    def __init__(self, *, config: dict | None = None) -> None:
        self._config = dict(config) if isinstance(config, dict) else {}
        self._ctx: ModeContext | None = None
        self._trial: TimeTrial | None = None
        self._allow_marker_edit = bool(self._config.get("allow_marker_edit", True))
        self._leaderboard_rank: tuple[int, int] | None = None

    def bindings(self) -> ModeBindings:
        # F4 is reserved for the in-game console. Keep restart on a shifted chord.
        ev: list[tuple[str, callable]] = [("shift-f4", self._restart)]
        if self._allow_marker_edit:
            ev += [
                ("f5", self._set_start_marker),
                ("f6", self._set_finish_marker),
                ("f7", self._clear_course),
                ("f8", self._export_course_to_run_json),
                ("f9", self._export_spawn_to_run_json),
            ]
        return ModeBindings(events=ev)

    def on_enter(self, *, ctx: ModeContext) -> None:
        self._ctx = ctx
        map_id = ctx.map_id

        # Course volumes: prefer run.json config, then local override (dev helper).
        start = aabb_from_json(self._config.get("start_aabb"))
        finish = aabb_from_json(self._config.get("finish_aabb"))
        if start is None or finish is None:
            ov = get_time_trial_course_override(map_id=map_id)
            if isinstance(ov, dict):
                start = start or aabb_from_json(ov.get("start_aabb"))
                finish = finish or aabb_from_json(ov.get("finish_aabb"))

        pb = get_time_trial_pb_seconds(map_id=map_id)
        self._trial = TimeTrial(map_id=map_id, course=CourseSpec(start=start, finish=finish), pb_seconds=pb)
        self._leaderboard_rank = None
        self._refresh_hud(hint_event=None)

    def on_exit(self) -> None:
        if self._ctx is not None:
            self._ctx.ui.set_time_trial_hud(None)
        self._ctx = None
        self._trial = None
        self._leaderboard_rank = None

    def spawn_override(self) -> SpawnSpec | None:
        # Spawn is controlled by run.json "spawn" at the map bundle level, not by the mode.
        return None

    def on_reset_requested(self) -> bool:
        # Respawn cancels the current attempt (core game handles the actual respawn).
        if self._trial is not None:
            self._trial.cancel_run()
            self._leaderboard_rank = None
            self._refresh_hud(hint_event=None)
        return False

    def tick(self, *, now: float, player_pos: LVector3f) -> None:
        tt = self._trial
        if tt is None:
            return
        ev = tt.tick(now=now, pos=player_pos)
        if ev == "finish" and tt.last_seconds is not None:
            new_pb, _last, rank = record_time_trial_run(map_id=tt.map_id, seconds=tt.last_seconds, finished_at=time.time())
            if new_pb is not None:
                tt.pb_seconds = new_pb
            self._leaderboard_rank = rank
        self._refresh_hud(hint_event=ev)

    def _restart(self) -> None:
        if self._ctx is None:
            return
        if self._trial is not None:
            self._trial.cancel_run()
            self._leaderboard_rank = None
        self._ctx.host.request_respawn()

    def _set_start_marker(self) -> None:
        if self._ctx is None or self._trial is None:
            return
        half_xy = float(self._ctx.tuning.course_marker_half_extent_xy)
        half_z = float(self._ctx.tuning.course_marker_half_extent_z)
        start = make_marker_aabb(pos=self._ctx.host.player_pos(), half_xy=half_xy, half_z=half_z)
        self._trial.course = CourseSpec(start=start, finish=self._trial.course.finish)
        set_time_trial_course_override(
            map_id=self._trial.map_id,
            course={
                "start_aabb": aabb_to_json(self._trial.course.start) if self._trial.course.start is not None else None,
                "finish_aabb": aabb_to_json(self._trial.course.finish) if self._trial.course.finish is not None else None,
            },
        )
        self._trial.cancel_run()
        self._leaderboard_rank = None
        self._refresh_hud(hint_event="start")

    def _set_finish_marker(self) -> None:
        if self._ctx is None or self._trial is None:
            return
        half_xy = float(self._ctx.tuning.course_marker_half_extent_xy)
        half_z = float(self._ctx.tuning.course_marker_half_extent_z)
        finish = make_marker_aabb(pos=self._ctx.host.player_pos(), half_xy=half_xy, half_z=half_z)
        self._trial.course = CourseSpec(start=self._trial.course.start, finish=finish)
        set_time_trial_course_override(
            map_id=self._trial.map_id,
            course={
                "start_aabb": aabb_to_json(self._trial.course.start) if self._trial.course.start is not None else None,
                "finish_aabb": aabb_to_json(self._trial.course.finish) if self._trial.course.finish is not None else None,
            },
        )
        self._trial.cancel_run()
        self._leaderboard_rank = None
        self._refresh_hud(hint_event="finish")

    def _clear_course(self) -> None:
        if self._trial is None:
            return
        self._trial.course = CourseSpec()
        self._trial.cancel_run()
        self._leaderboard_rank = None
        set_time_trial_course_override(map_id=self._trial.map_id, course=None)
        self._refresh_hud(hint_event=None)

    def _refresh_hud(self, *, hint_event: str | None) -> None:
        if self._ctx is None:
            return
        ui = self._ctx.ui
        tt = self._trial
        if tt is None:
            ui.set_time_trial_hud(None)
            return

        if not tt.course.is_complete():
            ui.set_time_trial_hud("TT: missing start/finish (set F5/F6 or add run.json)")
            return

        now = self._ctx.host.now()
        cur = tt.current_seconds(now=now)
        pb = tt.pb_seconds
        last = tt.last_seconds

        def fmt(sec: float) -> str:
            m = int(sec // 60.0)
            s = sec - (m * 60.0)
            if m > 0:
                return f"{m}:{s:06.3f}"
            return f"{s:0.3f}"

        parts: list[str] = []
        if cur is not None:
            parts.append(f"Run {fmt(cur)}")
        elif last is not None:
            parts.append(f"Last {fmt(last)}")
        else:
            parts.append("Run ---.---")
        parts.append(f"PB {fmt(pb)}" if pb is not None else "PB ---.---")
        if self._leaderboard_rank is not None:
            r, n = self._leaderboard_rank
            parts.append(f"Rank {r}/{n}")
        if hint_event == "start":
            parts.append("[START]")
        elif hint_event == "finish":
            parts.append("[FINISH]")
        ui.set_time_trial_hud(" | ".join(parts))

    def _export_course_to_run_json(self) -> None:
        """
        Dev helper: write Start/Finish volumes into <bundle>/run.json so the mode is shareable with the map bundle.
        """

        if self._ctx is None or self._trial is None or self._ctx.bundle_root is None:
            return
        if not self._trial.course.is_complete():
            self._ctx.ui.set_time_trial_hud("TT: cannot export (missing start/finish)")
            return

        root = Path(self._ctx.bundle_root)
        p = run_json_path_for_bundle_ref(root)
        payload: dict = {}
        if p.exists():
            try:
                old = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    payload = dict(old)
            except Exception:
                payload = {}
        payload["mode"] = "time_trial"
        cfg = dict(payload.get("config")) if isinstance(payload.get("config"), dict) else {}
        cfg["start_aabb"] = aabb_to_json(self._trial.course.start)
        cfg["finish_aabb"] = aabb_to_json(self._trial.course.finish)
        payload["config"] = cfg
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._ctx.ui.set_time_trial_hud("TT: exported course to run.json")

    def _export_spawn_to_run_json(self) -> None:
        """
        Dev helper: write spawn override into <bundle>/run.json from current player position/yaw.
        """

        if self._ctx is None or self._ctx.bundle_root is None:
            return
        root = Path(self._ctx.bundle_root)
        p = run_json_path_for_bundle_ref(root)
        payload: dict = {}
        if p.exists():
            try:
                old = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(old, dict):
                    payload = dict(old)
            except Exception:
                payload = {}
        pos = self._ctx.host.player_pos()
        payload["spawn"] = {"position": [float(pos.x), float(pos.y), float(pos.z)], "yaw": float(self._ctx.host.player_yaw_deg())}
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._ctx.ui.set_time_trial_hud("TT: exported spawn to run.json")
