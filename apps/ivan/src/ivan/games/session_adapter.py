"""
Race adapter implementing the mode-agnostic GameSession protocol.

Wraps RaceRuntime and exposes a uniform API for the network server,
preserving wire compatibility with existing protocol payloads.
"""

from __future__ import annotations

from typing import Any

from panda3d.core import LVector3f

from ivan.games.race_runtime import RaceCourse, RaceEvent, RaceRuntime
from ivan.games.game_session import GameSession


class RaceSessionAdapter:
    """Adapts RaceRuntime to the GameSession protocol."""

    def __init__(self, *, initial_course: RaceCourse | None = None) -> None:
        self._runtime = RaceRuntime()
        if initial_course is not None:
            self._runtime.set_course(initial_course)

    def set_initial_course(self, course: Any | None) -> None:
        """Set race course directly (GameSession protocol)."""
        self._runtime.set_course(course if isinstance(course, RaceCourse) else None)

    def set_course(self, course: RaceCourse | None) -> None:
        """Set race course directly (backward-compat alias for app/editor)."""
        self.set_initial_course(course)

    def set_course_from_games_payload(self, payload: dict[str, Any] | None) -> bool:
        return self._runtime.set_course_from_games_payload(payload)

    def has_course(self) -> bool:
        return self._runtime.has_course()

    def games_payload(self) -> dict[str, Any] | None:
        return self._runtime.games_payload()

    def interact(
        self,
        *,
        player_id: int,
        pos: LVector3f,
        now: float,
    ) -> list[RaceEvent]:
        return self._runtime.interact(player_id=player_id, pos=pos, now=now)

    def consume_teleport_target(self, *, player_id: int) -> LVector3f | None:
        return self._runtime.consume_teleport_target(player_id=player_id)

    def is_player_frozen(self, *, player_id: int) -> bool:
        return self._runtime.is_player_frozen(player_id=player_id)

    def tick(
        self,
        *,
        now: float,
        player_positions: dict[int, LVector3f],
    ) -> list[RaceEvent]:
        return self._runtime.tick(now=now, player_positions=player_positions)

    def remove_player(self, *, player_id: int) -> None:
        self._runtime.remove_player(player_id=player_id)

    def export_state_payload(self) -> dict[str, Any]:
        """Returns game_state dict with race key for wire compatibility."""
        return {"race": self._runtime.export_state_payload()}

    def event_to_payload(self, event: RaceEvent, *, seq: int) -> dict[str, Any]:
        return RaceRuntime.event_to_payload(event, seq=seq)

    @property
    def status(self) -> str:
        return self._runtime.status


def create_race_session(*, initial_course: RaceCourse | None = None) -> GameSession:
    """Factory for the default race game session used by the server."""
    return RaceSessionAdapter(initial_course=initial_course)
