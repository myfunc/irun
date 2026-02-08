from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from panda3d.core import LVector3f

from ivan.physics.tuning import PhysicsTuning
from ivan.ui.debug_ui import DebugUI


@dataclass(frozen=True)
class SpawnSpec:
    position: LVector3f
    yaw_deg: float


@dataclass(frozen=True)
class ModeBindings:
    """
    Extra Panda3D event bindings to install while the mode is active.
    Each entry is (event_name, callback).
    """

    events: list[tuple[str, Callable[[], None]]]


class ModeHost(Protocol):
    def request_respawn(self) -> None: ...
    def player_pos(self) -> LVector3f: ...
    def player_yaw_deg(self) -> float: ...
    def now(self) -> float: ...


@dataclass(frozen=True)
class ModeContext:
    map_id: str
    bundle_root: str | None
    tuning: PhysicsTuning
    ui: DebugUI
    host: ModeHost


class GameMode(Protocol):
    id: str

    def bindings(self) -> ModeBindings: ...

    def on_enter(self, *, ctx: ModeContext) -> None: ...

    def on_exit(self) -> None: ...

    def spawn_override(self) -> SpawnSpec | None: ...

    def on_reset_requested(self) -> bool: ...

    def tick(self, *, now: float, player_pos: LVector3f) -> None: ...
