from __future__ import annotations

from panda3d.core import LVector3f

from ivan.modes.base import GameMode, ModeBindings, ModeContext, SpawnSpec


class FreeRunMode(GameMode):
    id = "free_run"

    def __init__(self, *, config: dict | None = None) -> None:
        self._config = dict(config) if isinstance(config, dict) else {}
        self._ctx: ModeContext | None = None

    def bindings(self) -> ModeBindings:
        return ModeBindings(events=[])

    def on_enter(self, *, ctx: ModeContext) -> None:
        self._ctx = ctx
        # Ensure mode-specific HUD elements are cleared.
        ctx.ui.set_time_trial_hud(None)

    def on_exit(self) -> None:
        self._ctx = None

    def spawn_override(self) -> SpawnSpec | None:
        return None

    def on_reset_requested(self) -> bool:
        # Let the core game handle respawn.
        return False

    def tick(self, *, now: float, player_pos: LVector3f) -> None:
        # No-op.
        _ = (now, player_pos)
