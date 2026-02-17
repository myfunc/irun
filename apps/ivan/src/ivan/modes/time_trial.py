from __future__ import annotations

import json
import time
from pathlib import Path

from panda3d.core import LVector3f

from ivan.course.time_trial import CourseSpec, TimeTrial, make_marker_cylinder
from ivan.course.volumes import (
    AABBVolume,
    CylinderVolume,
    aabb_from_json,
    aabb_to_json,
    cylinder_from_json,
    cylinder_to_json,
)
from ivan.maps.bundle_io import run_json_path_for_bundle_ref
from ivan.modes.base import GameMode, ModeBindings, ModeContext, SpawnSpec
from ivan.state import (
    get_time_trial_course_override,
    get_time_trial_leaderboard,
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
        self._leaderboard: list[float] = []

    def bindings(self) -> ModeBindings:
        # F4 is reserved for the in-game console. Keep restart on a shifted chord.
        ev: list[tuple[str, callable]] = [("shift-f4", self._restart)]
        if self._allow_marker_edit:
            ev += [
                ("5", self._set_start_marker),
                ("6", self._set_finish_marker),
                # Legacy aliases kept for compatibility with existing docs/workflows.
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

        start, finish = self._load_course_volumes(map_id=map_id)
        pb = get_time_trial_pb_seconds(map_id=map_id)
        self._trial = TimeTrial(map_id=map_id, course=CourseSpec(start=start, finish=finish), pb_seconds=pb)
        self._leaderboard_rank = None
        self._leaderboard = get_time_trial_leaderboard(map_id=map_id, limit=10)
        self._sync_marker_visuals()
        self._refresh_hud(hint_event=None)

    def on_exit(self) -> None:
        if self._ctx is not None:
            self._ctx.ui.set_time_trial_hud(None)
            self._ctx.host.set_time_trial_markers(start=None, finish=None)
        self._ctx = None
        self._trial = None
        self._leaderboard_rank = None
        self._leaderboard = []

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
            self._leaderboard = get_time_trial_leaderboard(map_id=tt.map_id, limit=10)
        self._refresh_hud(hint_event=ev)

    def _load_course_volumes(self, *, map_id: str) -> tuple[AABBVolume | CylinderVolume | None, AABBVolume | CylinderVolume | None]:
        # Prefer circle volumes, but keep AABB compatibility for existing run.json/state.
        start: AABBVolume | CylinderVolume | None = cylinder_from_json(self._config.get("start_circle"))
        finish: AABBVolume | CylinderVolume | None = cylinder_from_json(self._config.get("finish_circle"))
        start = start or aabb_from_json(self._config.get("start_aabb"))
        finish = finish or aabb_from_json(self._config.get("finish_aabb"))
        if start is not None and finish is not None:
            return start, finish
        ov = get_time_trial_course_override(map_id=map_id)
        if isinstance(ov, dict):
            start = start or cylinder_from_json(ov.get("start_circle")) or aabb_from_json(ov.get("start_aabb"))
            finish = finish or cylinder_from_json(ov.get("finish_circle")) or aabb_from_json(ov.get("finish_aabb"))
        return start, finish

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
        radius = float(self._ctx.tuning.course_marker_half_extent_xy)
        half_z = float(self._ctx.tuning.course_marker_half_extent_z)
        start = make_marker_cylinder(pos=self._ctx.host.player_pos(), radius=radius, half_z=half_z)
        self._trial.course = CourseSpec(start=start, finish=self._trial.course.finish)
        self._save_course_override()
        self._trial.cancel_run()
        self._leaderboard_rank = None
        self._sync_marker_visuals()
        self._refresh_hud(hint_event="start")

    def _set_finish_marker(self) -> None:
        if self._ctx is None or self._trial is None:
            return
        radius = float(self._ctx.tuning.course_marker_half_extent_xy)
        half_z = float(self._ctx.tuning.course_marker_half_extent_z)
        finish = make_marker_cylinder(pos=self._ctx.host.player_pos(), radius=radius, half_z=half_z)
        self._trial.course = CourseSpec(start=self._trial.course.start, finish=finish)
        self._save_course_override()
        self._trial.cancel_run()
        self._leaderboard_rank = None
        self._sync_marker_visuals()
        self._refresh_hud(hint_event="finish")

    def _save_course_override(self) -> None:
        tt = self._trial
        if tt is None:
            return
        start = tt.course.start
        finish = tt.course.finish
        set_time_trial_course_override(
            map_id=tt.map_id,
            course={
                "start_circle": cylinder_to_json(start) if isinstance(start, CylinderVolume) else None,
                "finish_circle": cylinder_to_json(finish) if isinstance(finish, CylinderVolume) else None,
                # Keep legacy keys for old readers/tools.
                "start_aabb": aabb_to_json(start) if isinstance(start, AABBVolume) else None,
                "finish_aabb": aabb_to_json(finish) if isinstance(finish, AABBVolume) else None,
            },
        )

    def _clear_course(self) -> None:
        if self._trial is None:
            return
        self._trial.course = CourseSpec()
        self._trial.cancel_run()
        self._leaderboard_rank = None
        set_time_trial_course_override(map_id=self._trial.map_id, course=None)
        self._sync_marker_visuals()
        self._refresh_hud(hint_event=None)

    def _sync_marker_visuals(self) -> None:
        if self._ctx is None or self._trial is None:
            return
        self._ctx.host.set_time_trial_markers(
            start=self._trial.course.start,
            finish=self._trial.course.finish,
        )

    @staticmethod
    def _fmt(sec: float) -> str:
        m = int(sec // 60.0)
        s = sec - (m * 60.0)
        if m > 0:
            return f"{m}:{s:06.3f}"
        return f"{s:0.3f}"

    def _refresh_hud(self, *, hint_event: str | None) -> None:
        if self._ctx is None:
            return
        ui = self._ctx.ui
        tt = self._trial
        if tt is None:
            ui.set_time_trial_hud(None)
            return

        if not tt.course.is_complete():
            if self._ctx.host.race_leaderboard_held():
                rows = [f"{idx}. {self._fmt(sec)}" for idx, sec in enumerate(self._leaderboard[:8], start=1)]
                if rows:
                    ui.set_time_trial_hud("RACE: set start (5) and finish (6)\nBEST TIMES\n" + "\n".join(rows))
                    return
                ui.set_time_trial_hud("RACE: set start (5) and finish (6)\nBEST TIMES\n(no runs yet)")
                return
            ui.set_time_trial_hud("RACE: set start (5) and finish (6)")
            return

        now = self._ctx.host.now()
        cur = tt.current_seconds(now=now)
        pb = tt.pb_seconds
        last = tt.last_seconds

        parts: list[str] = ["RACE"]
        if cur is not None:
            parts.append(f"Run {self._fmt(cur)}")
        elif last is not None:
            parts.append(f"Last {self._fmt(last)}")
        else:
            parts.append("Run ---.---")
        parts.append(f"PB {self._fmt(pb)}" if pb is not None else "PB ---.---")
        if self._leaderboard_rank is not None:
            r, n = self._leaderboard_rank
            parts.append(f"Rank {r}/{n}")
        if hint_event == "start":
            parts.append("[START]")
        elif hint_event == "finish":
            parts.append("[FINISH]")

        if self._ctx.host.race_leaderboard_held():
            rows = [f"{idx}. {self._fmt(sec)}" for idx, sec in enumerate(self._leaderboard[:8], start=1)]
            if rows:
                ui.set_time_trial_hud(" | ".join(parts) + "\nBEST TIMES\n" + "\n".join(rows))
                return
            ui.set_time_trial_hud(" | ".join(parts) + "\nBEST TIMES\n(no runs yet)")
            return
        ui.set_time_trial_hud(" | ".join(parts))

    def _export_course_to_run_json(self) -> None:
        """
        Dev helper: write Start/Finish volumes into <bundle>/run.json so the mode is shareable with the map bundle.
        """

        if self._ctx is None or self._trial is None or self._ctx.bundle_root is None:
            return
        if not self._trial.course.is_complete():
            self._ctx.ui.set_time_trial_hud("RACE: cannot export (missing start/finish)")
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
        start = self._trial.course.start
        finish = self._trial.course.finish
        cfg["start_circle"] = cylinder_to_json(start) if isinstance(start, CylinderVolume) else None
        cfg["finish_circle"] = cylinder_to_json(finish) if isinstance(finish, CylinderVolume) else None
        # Keep legacy keys for compatibility if older courses still use AABB.
        cfg["start_aabb"] = aabb_to_json(start) if isinstance(start, AABBVolume) else None
        cfg["finish_aabb"] = aabb_to_json(finish) if isinstance(finish, AABBVolume) else None
        payload["config"] = cfg
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._ctx.ui.set_time_trial_hud("RACE: exported course to run.json")

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
        payload["spawn"] = {
            "position": [float(pos.x), float(pos.y), float(pos.z)],
            "yaw": float(self._ctx.host.player_yaw_deg()),
        }
        p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._ctx.ui.set_time_trial_hud("RACE: exported spawn to run.json")
