from __future__ import annotations

from panda3d.core import LVector3f

from ivan.game.camera_tilt_observer import CameraTiltObserver, motion_tilt_targets


def test_motion_tilt_targets_stationary_returns_zero() -> None:
    tilt = motion_tilt_targets(
        vel=LVector3f(0.0, 0.0, 0.0),
        yaw_deg=0.0,
        reference_speed=6.0,
    )
    assert tilt.roll == 0.0
    assert tilt.pitch == 0.0


def test_motion_tilt_targets_strafe_right_rolls_positive() -> None:
    # yaw 0 -> forward +Y, right +X
    tilt = motion_tilt_targets(
        vel=LVector3f(4.0, 0.0, 0.0),
        yaw_deg=0.0,
        reference_speed=6.0,
    )
    assert tilt.roll > 0.0
    assert tilt.pitch == 0.0


def test_motion_tilt_targets_backpedal_adds_pitch() -> None:
    # yaw 0 -> backpedal is -Y
    tilt = motion_tilt_targets(
        vel=LVector3f(0.0, -4.0, 0.0),
        yaw_deg=0.0,
        reference_speed=6.0,
    )
    assert tilt.pitch > 0.0


def test_camera_tilt_observer_smooths_and_is_snappy_for_large_step() -> None:
    obs = CameraTiltObserver()
    p1 = obs.observe(
        dt=0.016,
        target_roll=0.0,
        target_pitch=0.0,
        enabled=True,
    )
    p2 = obs.observe(
        dt=0.016,
        target_roll=6.0,
        target_pitch=1.2,
        enabled=True,
    )
    assert p1.roll == 0.0
    assert 0.0 < p2.roll < 6.0
    assert 0.0 < p2.pitch < 1.2

