"""
Mode-agnostic game-session interface for network server integration.

The server depends on this protocol instead of race-specific runtime internals,
allowing future game modes (e.g. capture-the-flag, deathmatch) to plug in via
adapter implementations while preserving wire compatibility.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from panda3d.core import LVector3f


@runtime_checkable
class GameSession(Protocol):
    """
    Protocol for authoritative game-session state and actions.

    Implementations (e.g. RaceSessionAdapter) wrap mode-specific runtimes
    and expose a uniform API for the network server.
    """

    def set_initial_course(self, course: Any | None) -> None:
        """
        Bootstrap: set initial course/level directly (e.g. RaceCourse).
        No-op for modes that do not support direct course setting.
        """
        ...

    def set_course_from_games_payload(self, payload: dict[str, Any] | None) -> bool:
        """Load session from games definitions payload. Returns True if applied."""
        ...

    def has_course(self) -> bool:
        """True if an active game definition is loaded."""
        ...

    def games_payload(self) -> dict[str, Any] | None:
        """Definitions payload for replication (games_v/games). None when no course."""
        ...

    def interact(
        self,
        *,
        player_id: int,
        pos: LVector3f,
        now: float,
    ) -> list[Any]:
        """Handle mission interaction (e.g. F at marker). Returns events to replicate."""
        ...

    def consume_teleport_target(self, *, player_id: int) -> LVector3f | None:
        """Consume and return pending teleport position for player, or None."""
        ...

    def is_player_frozen(self, *, player_id: int) -> bool:
        """True if player movement should be frozen (e.g. countdown)."""
        ...

    def tick(
        self,
        *,
        now: float,
        player_positions: dict[int, LVector3f],
    ) -> list[Any]:
        """Advance session one tick. Returns events to replicate."""
        ...

    def remove_player(self, *, player_id: int) -> None:
        """Remove player from session (disconnect)."""
        ...

    def export_state_payload(self) -> dict[str, Any]:
        """Full game_state dict for snapshot (e.g. {"race": {...}})."""
        ...

    def event_to_payload(self, event: Any, *, seq: int) -> dict[str, Any]:
        """Serialize event for game_events replication."""
        ...

    @property
    def status(self) -> str:
        """Session status (e.g. idle, lobby, intro, countdown, running, finished)."""
        ...
