from __future__ import annotations

from panda3d.core import LVector3f

from ivan.course.time_trial import make_marker_cylinder
from ivan.games.race_runtime import RaceCourse, RaceRuntime


def _course_with_two_checkpoints() -> RaceCourse:
    mission = make_marker_cylinder(pos=LVector3f(0.0, 0.0, 1.0), radius=2.8, half_z=2.0)
    start = make_marker_cylinder(pos=LVector3f(10.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    cp1 = make_marker_cylinder(pos=LVector3f(20.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    cp2 = make_marker_cylinder(pos=LVector3f(30.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    finish = make_marker_cylinder(pos=LVector3f(40.0, 0.0, 1.0), radius=2.2, half_z=2.0)
    return RaceCourse(mission_marker=mission, start=start, checkpoints=(cp1, cp2), finish=finish)


def _advance_to_running(rt: RaceRuntime) -> None:
    mission_center = LVector3f(0.0, 0.0, 1.0)
    _ = rt.interact(player_id=1, pos=mission_center, now=0.0)
    _ = rt.interact(player_id=1, pos=mission_center, now=0.1)
    _ = rt.tick(now=1.1, player_positions={1: mission_center})
    _ = rt.tick(now=2.1, player_positions={1: mission_center})
    _ = rt.tick(now=3.1, player_positions={1: mission_center})
    _ = rt.tick(now=4.1, player_positions={1: mission_center})
    assert rt.status == "running"


def test_race_runtime_lobby_intro_countdown_and_go_flow() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())

    mission_center = LVector3f(0.0, 0.0, 1.0)
    ev1 = rt.interact(player_id=1, pos=mission_center, now=0.0)
    assert [e.kind for e in ev1] == ["race_lobby_join"]
    assert rt.status == "lobby"

    ev2 = rt.interact(player_id=1, pos=mission_center, now=0.1)
    assert [e.kind for e in ev2] == ["race_intro"]
    assert rt.status == "intro"
    assert rt.is_player_frozen(player_id=1) is True

    tp = rt.consume_teleport_target(player_id=1)
    assert tp is not None

    ev3 = rt.tick(now=1.1, player_positions={1: mission_center})
    assert [e.kind for e in ev3] == ["race_countdown_tick"]
    assert ev3[0].countdown_value == 3

    ev4 = rt.tick(now=2.1, player_positions={1: mission_center})
    assert [e.kind for e in ev4] == ["race_countdown_tick"]
    assert ev4[0].countdown_value == 2

    ev5 = rt.tick(now=3.1, player_positions={1: mission_center})
    assert [e.kind for e in ev5] == ["race_countdown_tick"]
    assert ev5[0].countdown_value == 1

    ev6 = rt.tick(now=4.1, player_positions={1: mission_center})
    assert [e.kind for e in ev6] == ["race_go"]
    assert rt.status == "running"
    assert rt.is_player_frozen(player_id=1) is False
    assert rt.race_started_at == 4.1


def test_race_runtime_requires_ordered_checkpoint_progression() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())
    _advance_to_running(rt)

    # Finish before checkpoints should do nothing.
    ev0 = rt.tick(now=4.2, player_positions={1: LVector3f(40.0, 0.0, 1.0)})
    assert ev0 == []

    ev1 = rt.tick(now=4.3, player_positions={1: LVector3f(20.0, 0.0, 1.0)})
    assert [e.kind for e in ev1] == ["race_checkpoint_collected"]
    assert ev1[0].checkpoint_index == 0

    ev2 = rt.tick(now=4.4, player_positions={1: LVector3f(40.0, 0.0, 1.0)})
    assert ev2 == []

    ev3 = rt.tick(now=4.5, player_positions={1: LVector3f(30.0, 0.0, 1.0)})
    assert [e.kind for e in ev3] == ["race_checkpoint_collected"]
    assert ev3[0].checkpoint_index == 1

    ev4 = rt.tick(now=4.6, player_positions={1: LVector3f(40.0, 0.0, 1.0)})
    assert [e.kind for e in ev4] == ["race_finished", "race_all_finished"]
    assert ev4[0].player_id == 1
    assert rt.status == "finished"


def test_race_runtime_assigns_distinct_teleports_for_multiple_participants() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())
    mission_center = LVector3f(0.0, 0.0, 1.0)

    _ = rt.interact(player_id=1, pos=mission_center, now=0.0)
    join_ev = rt.interact(player_id=2, pos=mission_center, now=0.05)
    assert [e.kind for e in join_ev] == ["race_lobby_join"]
    _ = rt.interact(player_id=1, pos=mission_center, now=0.1)

    tp1 = rt.consume_teleport_target(player_id=1)
    tp2 = rt.consume_teleport_target(player_id=2)
    assert tp1 is not None and tp2 is not None
    assert float(tp1.x) != float(tp2.x)


def test_race_course_definition_payload_roundtrip() -> None:
    src = _course_with_two_checkpoints()
    payload = src.to_definition_payload(definition_id="race_test")
    out = RaceCourse.from_definition_payload(payload)
    assert out is not None
    assert out.is_complete() is True
    assert len(out.checkpoints) == 2
    assert abs(float(out.start.center_xyz[0]) - 10.0) < 1e-6
    assert abs(float(out.finish.center_xyz[0]) - 40.0) < 1e-6


def test_race_runtime_state_payload_roundtrip() -> None:
    src = RaceRuntime()
    src.set_course(_course_with_two_checkpoints())
    _advance_to_running(src)
    _ = src.tick(now=4.3, player_positions={1: LVector3f(20.0, 0.0, 1.0)})
    payload = src.export_state_payload()

    dst = RaceRuntime()
    dst.set_course(_course_with_two_checkpoints())
    dst.apply_authoritative_state_payload(payload)

    assert dst.status == "running"
    assert 1 in dst.participants
    assert dst.players[1].next_checkpoint_index == 1


def test_race_lobby_join_event_is_not_repeated_for_same_player() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())
    mission_center = LVector3f(0.0, 0.0, 1.0)

    _ = rt.interact(player_id=1, pos=mission_center, now=0.0)
    first_join = rt.interact(player_id=2, pos=mission_center, now=0.1)
    second_join = rt.interact(player_id=2, pos=mission_center, now=0.2)

    assert [e.kind for e in first_join] == ["race_lobby_join"]
    assert second_join == []


def test_race_interact_during_running_does_not_add_new_participant() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())
    _advance_to_running(rt)

    # Player 2 can press interact inside mission marker while race is running,
    # but should not be inserted into the active participant set.
    ev = rt.interact(player_id=2, pos=LVector3f(0.0, 0.0, 1.0), now=4.2)
    assert ev == []
    assert rt.participants == {1}


def test_race_restart_from_finished_resets_participants_to_starter() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())
    mission_center = LVector3f(0.0, 0.0, 1.0)
    _ = rt.interact(player_id=1, pos=mission_center, now=0.0)
    _ = rt.interact(player_id=2, pos=mission_center, now=0.1)
    _ = rt.interact(player_id=1, pos=mission_center, now=0.2)
    _ = rt.tick(now=1.2, player_positions={1: mission_center, 2: mission_center})
    _ = rt.tick(now=2.2, player_positions={1: mission_center, 2: mission_center})
    _ = rt.tick(now=3.2, player_positions={1: mission_center, 2: mission_center})
    _ = rt.tick(now=4.2, player_positions={1: mission_center, 2: mission_center})
    _ = rt.tick(now=4.3, player_positions={1: LVector3f(20.0, 0.0, 1.0), 2: LVector3f(20.0, 0.0, 1.0)})
    _ = rt.tick(now=4.4, player_positions={1: LVector3f(30.0, 0.0, 1.0), 2: LVector3f(30.0, 0.0, 1.0)})
    _ = rt.tick(now=4.5, player_positions={1: LVector3f(40.0, 0.0, 1.0), 2: LVector3f(40.0, 0.0, 1.0)})
    assert rt.status == "finished"

    restart_ev = rt.interact(player_id=1, pos=mission_center, now=5.0)
    assert [e.kind for e in restart_ev] == ["race_lobby_join"]
    assert rt.status == "lobby"
    assert rt.participants == {1}


def test_race_remove_player_reassigns_starter_in_lobby() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())
    mission_center = LVector3f(0.0, 0.0, 1.0)
    _ = rt.interact(player_id=1, pos=mission_center, now=0.0)
    _ = rt.interact(player_id=2, pos=mission_center, now=0.1)

    assert rt.status == "lobby"
    assert rt.starter_id == 1
    rt.remove_player(player_id=1)

    assert rt.status == "lobby"
    assert rt.starter_id == 2
    assert rt.participants == {2}


def test_race_remove_last_player_transitions_finished_to_idle() -> None:
    rt = RaceRuntime()
    rt.set_course(_course_with_two_checkpoints())
    mission_center = LVector3f(0.0, 0.0, 1.0)
    _ = rt.interact(player_id=1, pos=mission_center, now=0.0)
    _ = rt.interact(player_id=1, pos=mission_center, now=0.1)
    _ = rt.tick(now=1.1, player_positions={1: mission_center})
    _ = rt.tick(now=2.1, player_positions={1: mission_center})
    _ = rt.tick(now=3.1, player_positions={1: mission_center})
    _ = rt.tick(now=4.1, player_positions={1: mission_center})
    _ = rt.tick(now=4.2, player_positions={1: LVector3f(20.0, 0.0, 1.0)})
    _ = rt.tick(now=4.3, player_positions={1: LVector3f(30.0, 0.0, 1.0)})
    _ = rt.tick(now=4.4, player_positions={1: LVector3f(40.0, 0.0, 1.0)})
    assert rt.status == "finished"

    rt.remove_player(player_id=1)
    assert rt.status == "idle"
    assert rt.participants == set()
