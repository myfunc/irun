"""
Race mode: first-class mode using RaceRuntime (mission marker, intro, countdown, checkpoints).

Distinct from time_trial (legacy 2-marker start/finish). Race mode uses the games
module RaceRuntime for lobby/intro/countdown/running flow and ordered checkpoint progression.
"""

from __future__ import annotations

from panda3d.core import LVector3f

from ivan.modes.base import GameMode, ModeBindings, ModeContext, SpawnSpec


class RaceMode(GameMode):
    """
    Race mode: mission marker F to join, intro/countdown, ordered checkpoints, finish.

    Uses RaceRuntime (wired by app). Marker rendering and runtime tick are handled
    by the app; this mode provides bindings and lifecycle only.
    """

    id = "race"

    def __init__(self, *, config: dict | None = None) -> None:
        self._config = dict(config) if isinstance(config, dict) else {}
        self._ctx: ModeContext | None = None

    def bindings(self) -> ModeBindings:
        # F4 is reserved for in-game console. Restart on shifted chord.
        return ModeBindings(events=[("shift-f4", self._restart)])

    def on_enter(self, *, ctx: ModeContext) -> None:
        self._ctx = ctx

    def on_exit(self) -> None:
        if self._ctx is not None:
            self._ctx.ui.set_time_trial_hud(None)
            self._ctx.host.set_time_trial_markers(start=None, finish=None)
        self._ctx = None

    def spawn_override(self) -> SpawnSpec | None:
        return None

    def on_reset_requested(self) -> bool:
        return False

    def tick(self, *, now: float, player_pos: LVector3f) -> None:
        pass

    def _restart(self) -> None:
        if self._ctx is None:
            return
        self._ctx.host.request_respawn()
