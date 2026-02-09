from __future__ import annotations

from ivan.game.camera_height_observer import CameraHeightObserver


def test_camera_height_observer_disabled_returns_target() -> None:
    obs = CameraHeightObserver()
    out = obs.observe(dt=0.016, target_offset_z=0.42, enabled=False)
    assert out == 0.42


def test_camera_height_observer_smooths_large_step() -> None:
    obs = CameraHeightObserver()
    first = obs.observe(dt=0.016, target_offset_z=0.60, enabled=True)
    assert first == 0.60

    out = obs.observe(dt=0.016, target_offset_z=0.20, enabled=True)
    assert out < 0.60
    assert out > 0.20
