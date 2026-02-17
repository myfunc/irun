from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from panda3d.core import LVector3f

from ivan.course.volumes import CylinderVolume, cylinder_from_json, cylinder_to_json


@dataclass(frozen=True)
class RaceCourse:
    mission_marker: CylinderVolume | None = None
    start: CylinderVolume | None = None
    checkpoints: tuple[CylinderVolume, ...] = ()
    finish: CylinderVolume | None = None

    def is_complete(self) -> bool:
        return self.mission_marker is not None and self.start is not None and self.finish is not None

    def to_definition_payload(self, *, definition_id: str = "race_001") -> dict[str, Any]:
        return {
            "id": str(definition_id),
            "type": "race",
            "mission_marker": cylinder_to_json(self.mission_marker) if self.mission_marker is not None else None,
            "payload": {
                "start": cylinder_to_json(self.start) if self.start is not None else None,
                "checkpoints": [cylinder_to_json(cp) for cp in self.checkpoints],
                "finish": cylinder_to_json(self.finish) if self.finish is not None else None,
            },
        }

    @staticmethod
    def from_definition_payload(payload: dict[str, Any] | None) -> RaceCourse | None:
        if not isinstance(payload, dict):
            return None
        if str(payload.get("type") or "").strip().lower() != "race":
            return None
        race_payload = payload.get("payload")
        if not isinstance(race_payload, dict):
            return None
        mission = cylinder_from_json(payload.get("mission_marker"))
        start = cylinder_from_json(race_payload.get("start"))
        finish = cylinder_from_json(race_payload.get("finish"))
        if mission is None or start is None or finish is None:
            return None
        checkpoints_raw = race_payload.get("checkpoints")
        checkpoints: list[CylinderVolume] = []
        if isinstance(checkpoints_raw, list):
            for row in checkpoints_raw:
                cp = cylinder_from_json(row)
                if cp is not None:
                    checkpoints.append(cp)
        return RaceCourse(
            mission_marker=mission,
            start=start,
            checkpoints=tuple(checkpoints),
            finish=finish,
        )


@dataclass
class RacePlayerState:
    next_checkpoint_index: int = 0
    finished: bool = False
    elapsed_seconds: float | None = None


@dataclass(frozen=True)
class RaceEvent:
    kind: str
    player_id: int = 0
    checkpoint_index: int = -1
    countdown_value: int = 0
    elapsed_seconds: float | None = None


@dataclass
class RaceRuntime:
    course: RaceCourse | None = None
    status: str = "idle"  # idle | lobby | intro | countdown | running | finished
    starter_id: int | None = None
    participants: set[int] = field(default_factory=set)
    players: dict[int, RacePlayerState] = field(default_factory=dict)
    countdown_value: int = 3
    intro_until: float = 0.0
    countdown_next_at: float = 0.0
    race_started_at: float = 0.0
    teleport_targets: dict[int, LVector3f] = field(default_factory=dict)
    _inside_mission: dict[int, bool] = field(default_factory=dict)
    _inside_cp: dict[int, set[int]] = field(default_factory=dict)
    _inside_finish: dict[int, bool] = field(default_factory=dict)

    def clear(self) -> None:
        self.course = None
        self.status = "idle"
        self.starter_id = None
        self.participants.clear()
        self.players.clear()
        self.countdown_value = 3
        self.intro_until = 0.0
        self.countdown_next_at = 0.0
        self.race_started_at = 0.0
        self.teleport_targets.clear()
        self._inside_mission.clear()
        self._inside_cp.clear()
        self._inside_finish.clear()

    def set_course(self, course: RaceCourse | None) -> None:
        self.clear()
        self.course = course

    def games_payload(self) -> dict[str, Any] | None:
        if self.course is None:
            return None
        return {"definitions": [self.course.to_definition_payload()]}

    def set_course_from_games_payload(self, payload: dict[str, Any] | None) -> bool:
        self.set_course(None)
        if not isinstance(payload, dict):
            return False
        defs = payload.get("definitions")
        if not isinstance(defs, list):
            return False
        for row in defs:
            course = RaceCourse.from_definition_payload(row if isinstance(row, dict) else None)
            if course is None:
                continue
            self.set_course(course)
            return True
        return False

    def mission_marker(self) -> CylinderVolume | None:
        if self.course is None:
            return None
        return self.course.mission_marker

    def start_marker(self) -> CylinderVolume | None:
        if self.course is None:
            return None
        return self.course.start

    def checkpoint_markers(self) -> tuple[CylinderVolume, ...]:
        if self.course is None:
            return ()
        return self.course.checkpoints

    def finish_marker(self) -> CylinderVolume | None:
        if self.course is None:
            return None
        return self.course.finish

    def checkpoints_visible(self) -> bool:
        return self.status in {"intro", "countdown", "running", "finished"}

    def mission_visible(self) -> bool:
        return self.status in {"idle", "lobby", "finished"} and self.course is not None and self.course.mission_marker is not None

    def has_course(self) -> bool:
        return self.course is not None and self.course.is_complete()

    def export_state_payload(self) -> dict[str, Any]:
        players: list[dict[str, Any]] = []
        for pid in sorted(self.players.keys()):
            row = self.players.get(int(pid), RacePlayerState())
            players.append(
                {
                    "id": int(pid),
                    "next_checkpoint_index": int(row.next_checkpoint_index),
                    "finished": bool(row.finished),
                    "elapsed_seconds": float(row.elapsed_seconds) if row.elapsed_seconds is not None else None,
                }
            )
        return {
            "status": str(self.status),
            "starter_id": int(self.starter_id) if self.starter_id is not None else None,
            "participants": [int(pid) for pid in sorted(self.participants)],
            "countdown_value": int(self.countdown_value),
            "race_started_at": float(self.race_started_at),
            "players": players,
        }

    def apply_authoritative_state_payload(self, state: dict[str, Any] | None) -> None:
        if not isinstance(state, dict):
            return
        status_raw = str(state.get("status") or "idle").strip().lower()
        if status_raw not in {"idle", "lobby", "intro", "countdown", "running", "finished"}:
            status_raw = "idle"
        self.status = status_raw
        starter_raw = state.get("starter_id")
        self.starter_id = int(starter_raw) if isinstance(starter_raw, int) else None
        participants_raw = state.get("participants")
        participants: set[int] = set()
        if isinstance(participants_raw, list):
            for pid in participants_raw:
                if isinstance(pid, int) and int(pid) > 0:
                    participants.add(int(pid))
        self.participants = participants
        self.countdown_value = max(0, int(state.get("countdown_value") or 0))
        try:
            self.race_started_at = float(state.get("race_started_at") or 0.0)
        except Exception:
            self.race_started_at = 0.0

        players_payload = state.get("players")
        players: dict[int, RacePlayerState] = {}
        if isinstance(players_payload, list):
            for row in players_payload:
                if not isinstance(row, dict):
                    continue
                pid = int(row.get("id") or 0)
                if pid <= 0:
                    continue
                elapsed = row.get("elapsed_seconds")
                players[int(pid)] = RacePlayerState(
                    next_checkpoint_index=max(0, int(row.get("next_checkpoint_index") or 0)),
                    finished=bool(row.get("finished")),
                    elapsed_seconds=(float(elapsed) if isinstance(elapsed, (int, float)) else None),
                )
        for pid in self.participants:
            players.setdefault(int(pid), RacePlayerState())
        self.players = players
        self._inside_cp = {int(pid): set() for pid in self.participants}
        self._inside_finish = {int(pid): False for pid in self.participants}

    @staticmethod
    def event_to_payload(event: RaceEvent, *, seq: int) -> dict[str, Any]:
        return {
            "seq": int(seq),
            "kind": str(event.kind),
            "player_id": int(event.player_id),
            "checkpoint_index": int(event.checkpoint_index),
            "countdown_value": int(event.countdown_value),
            "elapsed_seconds": (float(event.elapsed_seconds) if event.elapsed_seconds is not None else None),
        }

    @staticmethod
    def event_from_payload(payload: dict[str, Any] | None) -> tuple[int, RaceEvent] | None:
        if not isinstance(payload, dict):
            return None
        seq = int(payload.get("seq") or 0)
        if seq <= 0:
            return None
        kind = str(payload.get("kind") or "").strip()
        if not kind:
            return None
        elapsed = payload.get("elapsed_seconds")
        ev = RaceEvent(
            kind=kind,
            player_id=int(payload.get("player_id") or 0),
            checkpoint_index=int(payload.get("checkpoint_index") or -1),
            countdown_value=int(payload.get("countdown_value") or 0),
            elapsed_seconds=(float(elapsed) if isinstance(elapsed, (int, float)) else None),
        )
        return (seq, ev)

    def is_player_frozen(self, *, player_id: int) -> bool:
        return self.status in {"intro", "countdown"} and int(player_id) in self.participants

    def consume_teleport_target(self, *, player_id: int) -> LVector3f | None:
        pos = self.teleport_targets.pop(int(player_id), None)
        return LVector3f(pos) if isinstance(pos, LVector3f) else None

    def remove_player(self, *, player_id: int) -> None:
        pid = int(player_id)
        self.participants.discard(pid)
        self.players.pop(pid, None)
        self.teleport_targets.pop(pid, None)
        self._inside_mission.pop(pid, None)
        self._inside_cp.pop(pid, None)
        self._inside_finish.pop(pid, None)
        if self.starter_id == pid:
            self.starter_id = next(iter(sorted(self.participants)), None)
        if not self.participants and self.status in {"lobby", "intro", "countdown", "running", "finished"}:
            self.status = "idle"

    @staticmethod
    def _inside_marker(marker: CylinderVolume | None, *, pos: LVector3f) -> bool:
        if marker is None:
            return False
        return bool(marker.contains_point(x=float(pos.x), y=float(pos.y), z=float(pos.z)))

    def interact(self, *, player_id: int, pos: LVector3f, now: float) -> list[RaceEvent]:
        player_id = int(player_id)
        if not self.has_course():
            return []
        if not self._inside_marker(self.course.mission_marker if self.course is not None else None, pos=pos):
            return []

        events: list[RaceEvent] = []
        if self.status in {"idle", "finished"}:
            # Start a fresh lobby window from the player that initiated this run.
            self.participants = {int(player_id)}
            self.players = {}
            self.teleport_targets.clear()
            self._inside_cp = {}
            self._inside_finish = {}
            self.status = "lobby"
            self.starter_id = player_id
            events.append(RaceEvent(kind="race_lobby_join", player_id=player_id))
            return events

        if self.status == "lobby":
            if self.starter_id is None:
                self.starter_id = player_id
            if player_id == self.starter_id:
                events.extend(self._begin_intro(now=now))
            else:
                if int(player_id) not in self.participants:
                    self.participants.add(int(player_id))
                    events.append(RaceEvent(kind="race_lobby_join", player_id=player_id))
            return events

        return events

    def _begin_intro(self, *, now: float) -> list[RaceEvent]:
        out: list[RaceEvent] = []
        self.status = "intro"
        self.players = {int(pid): RacePlayerState() for pid in self.participants}
        self._inside_cp = {int(pid): set() for pid in self.participants}
        self._inside_finish = {int(pid): False for pid in self.participants}
        self.intro_until = float(now) + 0.9
        self.countdown_value = 3
        self.countdown_next_at = self.intro_until
        self.race_started_at = 0.0
        self.teleport_targets.clear()
        start = self.start_marker()
        if start is not None:
            cx, cy, cz = start.center_xyz
            for idx, pid in enumerate(sorted(self.participants)):
                # Small deterministic offsets to avoid all players occupying exactly one point.
                offset = float(idx) * 0.55
                self.teleport_targets[int(pid)] = LVector3f(float(cx) + offset, float(cy), float(cz))
        out.append(RaceEvent(kind="race_intro"))
        return out

    def tick(self, *, now: float, player_positions: dict[int, LVector3f]) -> list[RaceEvent]:
        if not self.has_course():
            return []
        out: list[RaceEvent] = []
        now_f = float(now)

        if self.status == "intro":
            if now_f >= float(self.intro_until):
                self.status = "countdown"
                self.countdown_value = 3
                self.countdown_next_at = now_f + 1.0
                out.append(RaceEvent(kind="race_countdown_tick", countdown_value=3))
            return out

        if self.status == "countdown":
            if now_f >= float(self.countdown_next_at):
                self.countdown_value -= 1
                if self.countdown_value >= 1:
                    self.countdown_next_at = now_f + 1.0
                    out.append(RaceEvent(kind="race_countdown_tick", countdown_value=int(self.countdown_value)))
                else:
                    self.status = "running"
                    self.race_started_at = now_f
                    out.append(RaceEvent(kind="race_go"))
            return out

        if self.status != "running":
            return out

        checkpoints = self.checkpoint_markers()
        finish = self.finish_marker()
        if finish is None:
            return out

        for pid in sorted(self.participants):
            player = self.players.get(int(pid))
            pos = player_positions.get(int(pid))
            if player is None or pos is None or bool(player.finished):
                continue
            cp_idx = int(player.next_checkpoint_index)
            if cp_idx < len(checkpoints):
                marker = checkpoints[cp_idx]
                inside = bool(marker.contains_point(x=float(pos.x), y=float(pos.y), z=float(pos.z)))
                inside_set = self._inside_cp.setdefault(int(pid), set())
                if inside and cp_idx not in inside_set:
                    player.next_checkpoint_index = cp_idx + 1
                    inside_set.add(cp_idx)
                    out.append(
                        RaceEvent(
                            kind="race_checkpoint_collected",
                            player_id=int(pid),
                            checkpoint_index=int(cp_idx),
                        )
                    )
                if not inside and cp_idx in inside_set:
                    inside_set.remove(cp_idx)
                continue

            inside_finish = bool(finish.contains_point(x=float(pos.x), y=float(pos.y), z=float(pos.z)))
            was_inside = bool(self._inside_finish.get(int(pid), False))
            if inside_finish and not was_inside:
                elapsed = max(0.0, now_f - float(self.race_started_at))
                player.finished = True
                player.elapsed_seconds = float(elapsed)
                out.append(
                    RaceEvent(
                        kind="race_finished",
                        player_id=int(pid),
                        elapsed_seconds=float(elapsed),
                    )
                )
            self._inside_finish[int(pid)] = inside_finish

        if self.participants and all(bool(self.players.get(int(pid), RacePlayerState()).finished) for pid in self.participants):
            self.status = "finished"
            out.append(RaceEvent(kind="race_all_finished"))
        return out
