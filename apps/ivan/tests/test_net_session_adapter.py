"""
Tests for game-session adapter and server integration.

Verifies that RaceSessionAdapter implements GameSession and that the server
correctly uses the interface for race flows.
"""

from __future__ import annotations

from panda3d.core import LVector3f

from ivan.course.time_trial import make_marker_cylinder
from ivan.games.race_runtime import RaceCourse
from ivan.games.session_adapter import RaceSessionAdapter, create_race_session
from ivan.games.game_session import GameSession


def _course_with_two_checkpoints() -> RaceCourse:
    mission = make_marker_cylinder(pos=LVector3f(0.0, 0.0, 1.0), radius=2.8, half_z=2.0)
    start = make_marker_cylinder(pos=LVector3f(10.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    cp1 = make_marker_cylinder(pos=LVector3f(20.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    cp2 = make_marker_cylinder(pos=LVector3f(30.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    finish = make_marker_cylinder(pos=LVector3f(40.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    return RaceCourse(mission_marker=mission, start=start, checkpoints=(cp1, cp2), finish=finish)


def test_race_session_adapter_implements_game_session() -> None:
    """RaceSessionAdapter conforms to GameSession protocol."""
    adapter = RaceSessionAdapter()
    assert isinstance(adapter, GameSession)


def test_create_race_session_returns_game_session() -> None:
    """Factory returns a valid GameSession."""
    session = create_race_session(initial_course=_course_with_two_checkpoints())
    assert isinstance(session, GameSession)
    assert session.has_course() is True


def test_adapter_interact_and_tick_produce_events() -> None:
    """Adapter interact/tick return events that can be serialized."""
    session = RaceSessionAdapter(initial_course=_course_with_two_checkpoints())
    mission_center = LVector3f(0.0, 0.0, 1.0)

    ev1 = session.interact(player_id=1, pos=mission_center, now=0.0)
    assert len(ev1) == 1
    payload = session.event_to_payload(ev1[0], seq=1)
    assert payload["kind"] == "race_lobby_join"
    assert payload["seq"] == 1

    ev2 = session.interact(player_id=1, pos=mission_center, now=0.1)
    assert len(ev2) == 1
    payload2 = session.event_to_payload(ev2[0], seq=2)
    assert payload2["kind"] == "race_intro"


def test_adapter_export_state_payload_has_race_key() -> None:
    """export_state_payload returns wire-compatible dict with race key."""
    session = RaceSessionAdapter(initial_course=_course_with_two_checkpoints())
    session.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.0)
    session.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.1)

    state = session.export_state_payload()
    assert isinstance(state, dict)
    assert "race" in state
    assert state["race"]["status"] == "intro"


def test_adapter_set_initial_course() -> None:
    """Adapter implements GameSession.set_initial_course for bootstrap."""
    session: GameSession = RaceSessionAdapter()
    assert session.has_course() is False

    course = _course_with_two_checkpoints()
    session.set_initial_course(course)
    assert session.has_course() is True
    assert session.games_payload() is not None

    session.set_initial_course(None)
    assert session.has_course() is False


def test_adapter_set_course_from_games_payload() -> None:
    """Adapter accepts games payload from wire format."""
    session = RaceSessionAdapter()
    assert session.has_course() is False

    course = _course_with_two_checkpoints()
    games = course.to_definition_payload(definition_id="race_001")
    payload = {"definitions": [games]}

    ok = session.set_course_from_games_payload(payload)
    assert ok is True
    assert session.has_course() is True
    assert session.games_payload() is not None


def test_adapter_consume_teleport_after_intro() -> None:
    """consume_teleport_target returns position after intro starts."""
    session = RaceSessionAdapter(initial_course=_course_with_two_checkpoints())
    session.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.0)
    session.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.1)

    tp = session.consume_teleport_target(player_id=1)
    assert tp is not None
    assert abs(float(tp.x) - 10.0) < 1e-6


def test_adapter_is_player_frozen_during_countdown() -> None:
    """is_player_frozen True during intro/countdown."""
    session = RaceSessionAdapter(initial_course=_course_with_two_checkpoints())
    session.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.0)
    session.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.1)

    assert session.status == "intro"
    assert session.is_player_frozen(player_id=1) is True

    session.tick(now=1.1, player_positions={1: LVector3f(10.0, 0.0, 1.0)})
    session.tick(now=2.1, player_positions={1: LVector3f(10.0, 0.0, 1.0)})
    session.tick(now=3.1, player_positions={1: LVector3f(10.0, 0.0, 1.0)})
    session.tick(now=4.1, player_positions={1: LVector3f(10.0, 0.0, 1.0)})

    assert session.status == "running"
    assert session.is_player_frozen(player_id=1) is False


def test_adapter_remove_player() -> None:
    """remove_player clears player from session."""
    session = RaceSessionAdapter(initial_course=_course_with_two_checkpoints())
    session.interact(player_id=1, pos=LVector3f(0.0, 0.0, 1.0), now=0.0)
    session.interact(player_id=2, pos=LVector3f(0.0, 0.0, 1.0), now=0.05)

    session.remove_player(player_id=1)
    assert 1 not in session._runtime.participants
    assert session._runtime.starter_id == 2
