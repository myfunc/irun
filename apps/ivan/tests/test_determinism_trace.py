from __future__ import annotations

from panda3d.core import LVector3f

from ivan.game.animation_observer import AnimationObserver
from ivan.game.camera_observer import CameraObserver
from ivan.game.determinism import DeterminismTrace, deterministic_state_hash


def test_deterministic_state_hash_is_stable_for_same_quantized_state() -> None:
    h1 = deterministic_state_hash(
        pos=LVector3f(1.0004, 2.0, 3.0),
        vel=LVector3f(0.1, 0.2, 0.3),
        yaw_deg=11.111,
        pitch_deg=-2.345,
        grounded=True,
        state="ground",
        contact_count=2,
        jump_buffer_left=0.081,
        coyote_left=0.050,
    )
    h2 = deterministic_state_hash(
        pos=LVector3f(1.00049, 2.0, 3.0),
        vel=LVector3f(0.1, 0.2, 0.3),
        yaw_deg=11.111,
        pitch_deg=-2.345,
        grounded=True,
        state="ground",
        contact_count=2,
        jump_buffer_left=0.081,
        coyote_left=0.050,
    )
    assert h1 == h2


def test_deterministic_state_hash_changes_when_motion_state_changes() -> None:
    base = deterministic_state_hash(
        pos=LVector3f(1, 2, 3),
        vel=LVector3f(4, 5, 6),
        yaw_deg=10.0,
        pitch_deg=1.0,
        grounded=False,
        state="air",
        contact_count=0,
        jump_buffer_left=0.0,
        coyote_left=0.0,
    )
    changed = deterministic_state_hash(
        pos=LVector3f(1, 2, 3),
        vel=LVector3f(4, 5, 6),
        yaw_deg=10.0,
        pitch_deg=1.0,
        grounded=True,
        state="ground",
        contact_count=1,
        jump_buffer_left=0.1,
        coyote_left=0.1,
    )
    assert base != changed


def test_determinism_trace_rolls_and_resets() -> None:
    trace = DeterminismTrace(tick_rate_hz=60, seconds=2.0)
    h1 = trace.record(t=1.0, tick_hash="aaaa")
    h2 = trace.record(t=1.1, tick_hash="bbbb")
    assert h1 != h2
    assert trace.sample_count() == 2
    assert trace.latest_trace_hash() == h2
    trace.reset()
    assert trace.sample_count() == 0
    assert trace.latest_trace_hash() == ("0" * 16)


def test_camera_observer_smoothing_tracks_target_without_snap() -> None:
    cam = CameraObserver()
    p1 = cam.observe(
        target_pos=LVector3f(0, 0, 0),
        target_yaw=0.0,
        target_pitch=0.0,
        dt=0.016,
        smoothing_enabled=True,
        smoothing_hz=20.0,
        target_roll=0.0,
    )
    p2 = cam.observe(
        target_pos=LVector3f(10, 0, 0),
        target_yaw=90.0,
        target_pitch=10.0,
        dt=0.016,
        smoothing_enabled=True,
        smoothing_hz=20.0,
        target_roll=12.0,
    )
    assert p1.pos.x == 0.0
    assert 0.0 < float(p2.pos.x) < 10.0
    assert 0.0 < float(p2.yaw) < 90.0
    assert 0.0 < float(p2.roll) < 12.0


def test_animation_observer_only_outputs_offset_when_enabled() -> None:
    anim = AnimationObserver()
    off0 = anim.camera_bob_offset_z(enabled=False, time_s=1.0, horizontal_speed=5.0)
    off1 = anim.camera_bob_offset_z(enabled=True, time_s=1.0, horizontal_speed=5.0)
    assert off0 == 0.0
    assert off1 != 0.0
