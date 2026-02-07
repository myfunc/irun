from __future__ import annotations

import math
from pathlib import Path

from panda3d.core import LVector3f

from ivan.physics.player_controller import PlayerController
from ivan.physics.tuning import PhysicsTuning
from ivan.ui.debug_ui import DebugUI


def _make_controller(tuning: PhysicsTuning) -> PlayerController:
    return PlayerController(
        tuning=tuning,
        spawn_point=LVector3f(0, 0, 3),
        aabbs=[],
        collision=None,
    )


class _FakeHit:
    def __init__(self, has_hit: bool, normal: LVector3f) -> None:
        self._has_hit = has_hit
        self._normal = LVector3f(normal)

    def hasHit(self) -> bool:
        return self._has_hit

    def getHitNormal(self) -> LVector3f:
        return LVector3f(self._normal)

    def getHitFraction(self) -> float:
        return 0.5


class _FakeCollision:
    def update_player_sweep_shape(self, *, player_radius: float, player_half_height: float) -> None:
        _ = player_radius, player_half_height

    def sweep_closest(self, from_pos: LVector3f, to_pos: LVector3f):
        d = LVector3f(to_pos - from_pos)
        if abs(d.x) > 0.001 or abs(d.y) > 0.001:
            return _FakeHit(True, LVector3f(-1.0, 0.0, 0.0))
        return _FakeHit(False, LVector3f(0.0, 0.0, 1.0))


def test_all_numeric_debug_controls_exist_have_tooltips_and_are_wired() -> None:
    numeric_fields = [name for name, _lo, _hi in DebugUI.NUMERIC_CONTROLS]
    assert len(numeric_fields) == len(set(numeric_fields))
    assert "jump_speed" not in numeric_fields

    tuning_fields = set(PhysicsTuning.__annotations__.keys())
    for field in numeric_fields:
        assert field in tuning_fields, f"Missing tuning field for slider: {field}"
        assert field in DebugUI.FIELD_HELP, f"Missing tooltip for slider: {field}"
        tip = DebugUI.FIELD_HELP[field]
        assert "Lower:" in tip and "Higher:" in tip, f"Tooltip must explain Lower/Higher for {field}"

    src_root = Path(__file__).resolve().parents[1] / "src" / "ivan"
    runtime_src = (src_root / "physics" / "player_controller.py").read_text(encoding="utf-8") + "\n" + (
        src_root / "game.py"
    ).read_text(encoding="utf-8")
    for field in numeric_fields:
        assert f"tuning.{field}" in runtime_src, f"Slider field is not used at runtime: {field}"


def test_all_toggle_controls_have_tooltips_with_lower_higher_guidance() -> None:
    src_root = Path(__file__).resolve().parents[1] / "src" / "ivan"
    runtime_src = (src_root / "physics" / "player_controller.py").read_text(encoding="utf-8") + "\n" + (
        src_root / "game.py"
    ).read_text(encoding="utf-8")
    for field in DebugUI.TOGGLE_CONTROLS:
        assert field in PhysicsTuning.__annotations__
        assert field in DebugUI.FIELD_HELP
        tip = DebugUI.FIELD_HELP[field]
        assert "Lower" in tip and "Higher" in tip
        assert f"tuning.{field}" in runtime_src, f"Toggle field is not used at runtime: {field}"


def test_jump_height_controls_jump_velocity() -> None:
    low = PhysicsTuning(jump_height=0.6, gravity=24.0)
    high = PhysicsTuning(jump_height=2.4, gravity=24.0)
    low_ctrl = _make_controller(low)
    high_ctrl = _make_controller(high)
    assert high_ctrl._jump_up_speed() > low_ctrl._jump_up_speed()
    assert math.isclose(low_ctrl._jump_up_speed(), math.sqrt(2.0 * 24.0 * 0.6), rel_tol=1e-6)


def test_jump_accel_affects_air_acceleration_strength() -> None:
    low = PhysicsTuning(jump_accel=3.0, max_air_speed=12.0)
    high = PhysicsTuning(jump_accel=30.0, max_air_speed=12.0)
    low_ctrl = _make_controller(low)
    high_ctrl = _make_controller(high)

    low_ctrl.grounded = False
    high_ctrl.grounded = False
    wish = LVector3f(1, 0, 0)
    low_ctrl.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=False)
    high_ctrl.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=False)
    assert high_ctrl.vel.x > low_ctrl.vel.x


def test_air_counter_strafe_brake_strength_affects_deceleration() -> None:
    low = PhysicsTuning(air_counter_strafe_brake=1.0)
    high = PhysicsTuning(air_counter_strafe_brake=40.0)
    low_ctrl = _make_controller(low)
    high_ctrl = _make_controller(high)

    low_ctrl.grounded = False
    high_ctrl.grounded = False
    low_ctrl.vel = LVector3f(10, 0, 0)
    high_ctrl.vel = LVector3f(10, 0, 0)
    opposite = LVector3f(-1, 0, 0)
    low_ctrl.step(dt=0.016, wish_dir=opposite, yaw_deg=0.0, crouching=False)
    high_ctrl.step(dt=0.016, wish_dir=opposite, yaw_deg=0.0, crouching=False)
    assert abs(high_ctrl.vel.x) < abs(low_ctrl.vel.x)


def test_wall_clip_preserves_upward_jump_velocity_near_vertical_surface() -> None:
    ctrl = _make_controller(PhysicsTuning())
    ctrl.grounded = False
    ctrl.vel = LVector3f(3.0, 0.0, 7.0)
    n = LVector3f(-0.7, 0.0, 0.2)  # mostly wall-like contact normal

    clip_n = ctrl._choose_clip_normal(n)
    assert abs(clip_n.z) < 1e-6


def test_wallrun_does_not_cancel_upward_jump_velocity() -> None:
    tuning = PhysicsTuning(wallrun_enabled=True)
    ctrl = _make_controller(tuning)
    ctrl.grounded = False
    ctrl.vel = LVector3f(3.0, 0.0, 7.0)
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(-1.0, 0.0, 0.0)

    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    assert ctrl.vel.z > 0.0


def test_crouch_speed_multiplier_reduces_ground_acceleration() -> None:
    tuning = PhysicsTuning(crouch_speed_multiplier=0.4, crouch_enabled=True)
    stand_ctrl = _make_controller(tuning)
    crouch_ctrl = _make_controller(tuning)
    wish = LVector3f(1, 0, 0)

    stand_ctrl.grounded = True
    crouch_ctrl.grounded = True
    stand_ctrl.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=False)
    crouch_ctrl.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=True)

    stand_speed = math.sqrt(stand_ctrl.vel.x * stand_ctrl.vel.x + stand_ctrl.vel.y * stand_ctrl.vel.y)
    crouch_speed = math.sqrt(crouch_ctrl.vel.x * crouch_ctrl.vel.x + crouch_ctrl.vel.y * crouch_ctrl.vel.y)
    assert crouch_speed < stand_speed


def test_wall_detection_probe_refreshes_without_movement() -> None:
    tuning = PhysicsTuning()
    ctrl = PlayerController(
        tuning=tuning,
        spawn_point=LVector3f(0, 0, 3),
        aabbs=[],
        collision=_FakeCollision(),
    )
    ctrl.grounded = False
    ctrl._wall_contact_timer = 999.0
    ctrl._wall_normal = LVector3f(0, 0, 0)

    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    assert ctrl.has_wall_for_jump()
