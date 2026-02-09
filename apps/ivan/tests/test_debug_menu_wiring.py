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
    # Keep this check broad: tuning fields may be used outside game.py (e.g. in game modes).
    runtime_src = ""
    for p in sorted(src_root.rglob("*.py")):
        if "egg-info" in p.parts:
            continue
        runtime_src += p.read_text(encoding="utf-8") + "\n"
    for field in numeric_fields:
        assert f"tuning.{field}" in runtime_src, f"Slider field is not used at runtime: {field}"


def test_all_toggle_controls_have_tooltips_with_lower_higher_guidance() -> None:
    src_root = Path(__file__).resolve().parents[1] / "src" / "ivan"
    runtime_src = ""
    for p in sorted(src_root.rglob("*.py")):
        if "egg-info" in p.parts:
            continue
        runtime_src += p.read_text(encoding="utf-8") + "\n"
    for field in DebugUI.TOGGLE_CONTROLS:
        assert field in PhysicsTuning.__annotations__
        assert field in DebugUI.FIELD_HELP
        tip = DebugUI.FIELD_HELP[field]
        assert "Lower" in tip and "Higher" in tip
        assert f"tuning.{field}" in runtime_src, f"Toggle field is not used at runtime: {field}"


def test_jump_height_controls_jump_velocity() -> None:
    low = PhysicsTuning(jump_height=0.6, jump_apex_time=0.30)
    high = PhysicsTuning(jump_height=2.4, jump_apex_time=0.30)
    low_ctrl = _make_controller(low)
    high_ctrl = _make_controller(high)
    assert high_ctrl._jump_up_speed() > low_ctrl._jump_up_speed()
    assert math.isclose(low_ctrl._jump_up_speed(), (2.0 * 0.6) / 0.30, rel_tol=1e-6)


def test_air_gain_t90_affects_air_acceleration_strength() -> None:
    slow = PhysicsTuning(max_ground_speed=6.0, air_speed_mult=2.0, air_gain_t90=0.40)
    fast = PhysicsTuning(max_ground_speed=6.0, air_speed_mult=2.0, air_gain_t90=0.08)
    slow_ctrl = _make_controller(slow)
    fast_ctrl = _make_controller(fast)

    slow_ctrl.grounded = False
    fast_ctrl.grounded = False
    wish = LVector3f(1, 0, 0)
    slow_ctrl.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=False)
    fast_ctrl.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=False)
    assert fast_ctrl.vel.x > slow_ctrl.vel.x


def test_air_speed_multiplier_affects_air_top_speed() -> None:
    low = _make_controller(PhysicsTuning(max_ground_speed=6.0, air_speed_mult=1.0, air_gain_t90=0.08))
    high = _make_controller(PhysicsTuning(max_ground_speed=6.0, air_speed_mult=2.0, air_gain_t90=0.08))

    for _ in range(80):
        low.grounded = False
        high.grounded = False
        low.step(dt=0.016, wish_dir=LVector3f(1, 0, 0), yaw_deg=0.0, crouching=False)
        high.step(dt=0.016, wish_dir=LVector3f(1, 0, 0), yaw_deg=0.0, crouching=False)

    low_speed = math.sqrt(low.vel.x * low.vel.x + low.vel.y * low.vel.y)
    high_speed = math.sqrt(high.vel.x * high.vel.x + high.vel.y * high.vel.y)
    assert high_speed > low_speed


def test_surf_input_does_not_reverse_horizontal_direction_in_one_tick() -> None:
    tuning = PhysicsTuning(
        surf_enabled=True,
        air_gain_t90=0.03,
        surf_accel=80.0,
        max_ground_speed=6.0,
        air_speed_mult=4.0,
    )
    ctrl = _make_controller(tuning)
    ctrl.grounded = False
    ctrl.vel = LVector3f(10.0, 0.0, 0.0)
    ctrl._surf_contact_timer = 0.0
    ctrl._surf_normal = LVector3f(0.65, 0.0, 0.76)

    # Opposite wish should scrub speed first, not flip direction instantly.
    ctrl.step(dt=0.016, wish_dir=LVector3f(-1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)
    assert ctrl.vel.x >= 0.0


def test_surf_opposite_steer_redirects_momentum_without_killing_speed() -> None:
    tuning = PhysicsTuning(
        surf_enabled=True,
        air_gain_t90=0.045,
        surf_accel=60.0,
        max_ground_speed=6.0,
        air_speed_mult=4.0,
    )
    ctrl = _make_controller(tuning)
    ctrl.grounded = False
    ctrl.vel = LVector3f(12.0, 0.0, 0.0)
    ctrl._surf_contact_timer = 0.0
    ctrl._surf_normal = LVector3f(0.65, 0.0, 0.76)
    pre_hspeed = math.sqrt(ctrl.vel.x * ctrl.vel.x + ctrl.vel.y * ctrl.vel.y)

    ctrl.step(dt=0.016, wish_dir=LVector3f(-1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)

    post_hspeed = math.sqrt(ctrl.vel.x * ctrl.vel.x + ctrl.vel.y * ctrl.vel.y)
    assert post_hspeed > pre_hspeed * 0.40
    assert ctrl.vel.z > -0.30


def test_surf_accel_never_adds_downward_vertical_component() -> None:
    ctrl = _make_controller(PhysicsTuning(surf_enabled=True, surf_accel=60.0))
    ctrl.vel = LVector3f(8.0, 0.0, 0.0)
    # Downhill-biased projected wish direction.
    wish = LVector3f(0.8, 0.0, -0.6)
    ctrl._accelerate_surf_redirect(wish, wish_speed=20.0, accel=18.0, dt=0.016)
    assert ctrl.vel.z >= 0.0


def test_stale_surf_contact_does_not_apply_surf_accel_after_leaving_ramp() -> None:
    ctrl = _make_controller(PhysicsTuning(surf_enabled=True, air_gain_t90=0.045, surf_accel=60.0))
    ctrl.grounded = False
    ctrl.vel = LVector3f(0.0, 0.0, 0.0)
    # Old contact should not keep surf acceleration active.
    ctrl._surf_contact_timer = 0.12
    ctrl._surf_normal = LVector3f(0.7, 0.0, 0.7)

    # This input would create positive Z if stale surf acceleration were still applied.
    ctrl.step(dt=0.016, wish_dir=LVector3f(-1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)
    assert ctrl.vel.z < -0.35


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


def test_wallrun_sets_active_state_and_camera_roll_indicator() -> None:
    tuning = PhysicsTuning(wallrun_enabled=True)
    ctrl = _make_controller(tuning)
    ctrl.grounded = False
    ctrl.vel = LVector3f(4.0, 0.0, 0.0)
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(-1.0, 0.0, 0.0)

    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)

    assert ctrl.is_wallrunning()
    assert ctrl.wallrun_camera_roll_deg(yaw_deg=0.0) < -0.1


def test_wallrun_camera_roll_clears_soon_after_contact_loss() -> None:
    tuning = PhysicsTuning(wallrun_enabled=True)
    ctrl = _make_controller(tuning)
    ctrl.grounded = False
    ctrl._wallrun_active = True
    ctrl._wall_normal = LVector3f(-1.0, 0.0, 0.0)
    ctrl._wall_contact_timer = 0.12

    assert ctrl.wallrun_camera_roll_deg(yaw_deg=0.0) == 0.0


def test_wallrun_jump_biases_to_camera_forward_direction() -> None:
    tuning = PhysicsTuning(
        wallrun_enabled=True,
        walljump_enabled=True,
        wall_jump_cooldown=0.0,
        wall_jump_boost=7.5,
        enable_jump_buffer=False,
    )
    ctrl = _make_controller(tuning)
    ctrl.grounded = False
    ctrl.vel = LVector3f(5.0, 0.0, -1.0)
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)  # wall peel-away points +X
    ctrl.queue_jump()

    # Camera points +Y (yaw 0): wallrun jump should favor camera forward over pure wall normal.
    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, pitch_deg=0.0, crouching=False)

    assert ctrl.vel.z > 0.0
    assert ctrl.vel.y > abs(ctrl.vel.x)


def test_wallrun_sink_t90_controls_descent_response() -> None:
    fast = _make_controller(PhysicsTuning(wallrun_enabled=True, wallrun_sink_t90=0.08))
    slow = _make_controller(PhysicsTuning(wallrun_enabled=True, wallrun_sink_t90=0.60))
    for ctrl in (fast, slow):
        ctrl.grounded = False
        ctrl.vel = LVector3f(4.0, 0.0, -6.0)
        ctrl._wall_contact_timer = 0.0
        ctrl._wall_normal = LVector3f(-1.0, 0.0, 0.0)

    fast.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    slow.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    assert fast.vel.z > slow.vel.z


def test_slide_engage_applies_low_hull_without_entry_boost() -> None:
    ctrl = _make_controller(
        PhysicsTuning(
            slide_enabled=True,
            slide_stop_t90=4.0,
            max_ground_speed=6.0,
        )
    )
    ctrl.grounded = True
    ctrl.vel = LVector3f(2.0, 0.0, 0.0)
    stand_half = float(ctrl.player_half.z)

    ctrl.queue_slide(wish_dir=LVector3f(1.0, 0.0, 0.0), yaw_deg=0.0)
    ctrl.step(dt=0.016, wish_dir=LVector3f(1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)

    slide_speed = math.sqrt(ctrl.vel.x * ctrl.vel.x + ctrl.vel.y * ctrl.vel.y)
    assert ctrl.is_sliding()
    assert ctrl.player_half.z < stand_half
    assert slide_speed <= 2.0
    assert slide_speed > 1.8


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


def test_walljump_respects_cooldown() -> None:
    ctrl = _make_controller(PhysicsTuning(walljump_enabled=True, wall_jump_cooldown=1.0))
    ctrl.grounded = False
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)
    ctrl._wall_contact_point = LVector3f(10.0, 0.0, 2.0)
    assert ctrl.has_wall_for_jump()
    ctrl._apply_wall_jump(yaw_deg=0.0)

    # Still touching a wall but cooldown should block another jump.
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)
    ctrl._wall_contact_point = LVector3f(10.1, 0.0, 2.2)
    assert not ctrl.has_wall_for_jump()
    ctrl.step(dt=1.01, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)
    assert ctrl.has_wall_for_jump()


def test_walljump_not_allowed_while_grounded_even_with_wall_contact() -> None:
    ctrl = _make_controller(PhysicsTuning(walljump_enabled=True))
    ctrl.grounded = True
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)
    assert not ctrl.has_wall_for_jump()


def test_coyote_jump_window_allows_late_jump_when_enabled() -> None:
    tuning = PhysicsTuning(
        coyote_buffer_enabled=True,
        coyote_time=0.12,
        jump_height=1.2,
        jump_apex_time=0.30,
    )
    ctrl = _make_controller(tuning)
    ctrl.grounded = True

    # Prime coyote timer from grounded state.
    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    assert ctrl.grounded is False
    assert ctrl.coyote_left() > 0.0

    ctrl.queue_jump()
    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    assert ctrl.vel.z > 0.0


def test_slide_release_restores_standing_hull() -> None:
    ctrl = _make_controller(PhysicsTuning(slide_enabled=True, slide_stop_t90=4.0))
    ctrl.grounded = True
    stand_half = float(ctrl.player_half.z)

    ctrl.set_slide_held(held=True)
    ctrl.step(dt=0.016, wish_dir=LVector3f(1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)
    assert ctrl.is_sliding()
    assert ctrl.player_half.z < stand_half

    ctrl.set_slide_held(held=False)
    ctrl.step(dt=0.016, wish_dir=LVector3f(0.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)
    assert not ctrl.is_sliding()
    assert math.isclose(float(ctrl.player_half.z), stand_half, rel_tol=1e-6)


def test_slide_ignores_keyboard_strafe_and_uses_camera_yaw() -> None:
    ctrl = _make_controller(PhysicsTuning(slide_enabled=True, slide_stop_t90=4.0))
    ctrl.grounded = True
    ctrl.vel = LVector3f(0.0, 8.0, 0.0)
    ctrl.set_slide_held(held=True)
    ctrl.step(dt=0.016, wish_dir=LVector3f(0.0, 1.0, 0.0), yaw_deg=0.0, crouching=False)

    pre_dot = float(LVector3f(ctrl.vel.x, ctrl.vel.y, 0.0).dot(LVector3f(0.0, 1.0, 0.0)))
    ctrl.step(dt=0.016, wish_dir=LVector3f(1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)
    post_dot = float(LVector3f(ctrl.vel.x, ctrl.vel.y, 0.0).dot(LVector3f(0.0, 1.0, 0.0)))
    assert post_dot > pre_dot * 0.95


def test_slide_wasd_input_does_not_change_ground_slide_motion() -> None:
    left = _make_controller(PhysicsTuning(slide_enabled=True, slide_stop_t90=4.0))
    right = _make_controller(PhysicsTuning(slide_enabled=True, slide_stop_t90=4.0))
    for ctrl in (left, right):
        ctrl.grounded = True
        ctrl.vel = LVector3f(0.0, 10.0, 0.0)
        ctrl.set_slide_held(held=True)
        ctrl.step(dt=0.016, wish_dir=LVector3f(0.0, 1.0, 0.0), yaw_deg=0.0, crouching=False)

    left.step(dt=0.016, wish_dir=LVector3f(-1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)
    right.step(dt=0.016, wish_dir=LVector3f(1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)

    assert math.isclose(float(left.vel.x), float(right.vel.x), abs_tol=1e-5)
    assert math.isclose(float(left.vel.y), float(right.vel.y), abs_tol=1e-5)


def test_invariant_vmax_remains_authoritative_under_input() -> None:
    low = _make_controller(
        PhysicsTuning(
            max_ground_speed=4.0,
            run_t90=0.22,
            ground_stop_t90=0.10,
        )
    )
    high = _make_controller(
        PhysicsTuning(
            max_ground_speed=10.0,
            run_t90=0.22,
            ground_stop_t90=0.10,
        )
    )
    wish = LVector3f(1, 0, 0)

    for _ in range(90):
        low.grounded = True
        high.grounded = True
        low.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=False)
        high.step(dt=0.016, wish_dir=wish, yaw_deg=0.0, crouching=False)

    low_speed = math.sqrt(low.vel.x * low.vel.x + low.vel.y * low.vel.y)
    high_speed = math.sqrt(high.vel.x * high.vel.x + high.vel.y * high.vel.y)
    assert low_speed > 3.5
    assert high_speed > 9.0
    assert high_speed > low_speed * 2.2


def test_ground_friction_still_damps_speed_without_input() -> None:
    ctrl = _make_controller(
        PhysicsTuning(
            ground_stop_t90=0.15,
            custom_friction_enabled=True,
        )
    )
    ctrl.vel = LVector3f(8.0, 0.0, 0.0)

    for _ in range(40):
        ctrl.grounded = True
        ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)

    speed = math.sqrt(ctrl.vel.x * ctrl.vel.x + ctrl.vel.y * ctrl.vel.y)
    assert speed < 1.0


def test_ground_jump_tick_preserves_horizontal_speed() -> None:
    ctrl = _make_controller(
        PhysicsTuning(
            custom_friction_enabled=True,
            ground_stop_t90=0.05,
            enable_jump_buffer=False,
        )
    )
    ctrl.grounded = True
    ctrl.vel = LVector3f(9.0, 0.0, 0.0)
    ctrl.queue_jump()

    ctrl.step(dt=0.016, wish_dir=LVector3f(0.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)

    assert ctrl.vel.x > 8.8
    assert ctrl.vel.z > 0.0


def test_ground_jump_tick_preserves_horizontal_speed_with_move_input() -> None:
    ctrl = _make_controller(
        PhysicsTuning(
            custom_friction_enabled=True,
            run_t90=0.06,
            ground_stop_t90=0.05,
            max_ground_speed=6.0,
            enable_jump_buffer=False,
        )
    )
    ctrl.grounded = True
    ctrl.vel = LVector3f(12.0, 0.0, 0.0)
    ctrl.queue_jump()

    ctrl.step(dt=0.016, wish_dir=LVector3f(1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)

    assert ctrl.vel.x > 11.7
    assert ctrl.vel.z > 0.0


def test_corner_jump_uses_ground_jump_not_walljump() -> None:
    ctrl = _make_controller(
        PhysicsTuning(
            walljump_enabled=True,
            enable_jump_buffer=False,
            wall_jump_boost=7.0,
        )
    )
    ctrl.grounded = True
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)
    ctrl._wall_jump_lock_timer = 999.0
    ctrl.queue_jump()

    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)

    # Ground jump path should win; walljump should not inject horizontal boost.
    assert abs(ctrl.vel.x) < 1e-5
    assert abs(ctrl.vel.y) < 1e-5
    assert ctrl.vel.z > 0.0


def test_ground_jump_does_not_reapply_in_air_on_next_frame() -> None:
    ctrl = _make_controller(
        PhysicsTuning(
            autojump_enabled=True,
            walljump_enabled=True,
            wall_jump_boost=7.0,
            enable_jump_buffer=False,
        )
    )

    # Frame 1: normal grounded jump near wall contact.
    ctrl.grounded = True
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)
    ctrl.queue_jump()
    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)
    first_jump_vz = ctrl.vel.z
    assert first_jump_vz > 0.0

    # Frame 2: no second jump should be applied while airborne.
    ctrl.step(dt=0.016, wish_dir=LVector3f(0, 0, 0), yaw_deg=0.0, crouching=False)

    # No second jump re-application should happen.
    assert ctrl.vel.z < first_jump_vz


def test_can_walljump_multiple_times_in_air_on_different_walls() -> None:
    ctrl = _make_controller(PhysicsTuning(walljump_enabled=True, wall_jump_cooldown=0.0))
    ctrl.grounded = False
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(1.0, 0.0, 0.0)
    ctrl._wall_contact_point = LVector3f(10.0, 0.0, 2.0)
    assert ctrl.has_wall_for_jump()
    ctrl._apply_wall_jump(yaw_deg=0.0)

    # Different wall plane in same airtime should be allowed.
    ctrl._wall_contact_timer = 0.0
    ctrl._wall_normal = LVector3f(0.0, 1.0, 0.0)
    ctrl._wall_contact_point = LVector3f(0.0, 10.0, 2.0)
    assert ctrl.has_wall_for_jump()


def test_surf_strafe_accelerates_on_slanted_surface() -> None:
    base = _make_controller(PhysicsTuning(surf_enabled=True, surf_accel=24.0))
    strafe = _make_controller(PhysicsTuning(surf_enabled=True, surf_accel=24.0))

    for ctrl in (base, strafe):
        ctrl.grounded = False
        ctrl.vel = LVector3f(2.0, 3.0, -1.5)
        ctrl._set_surf_contact(LVector3f(0.74, 0.0, 0.66))

    base.step(dt=0.016, wish_dir=LVector3f(0.0, 1.0, 0.0), yaw_deg=0.0, crouching=False)
    strafe.step(dt=0.016, wish_dir=LVector3f(1.0, 0.0, 0.0), yaw_deg=0.0, crouching=False)
    assert strafe.vel.x > base.vel.x


def test_grapple_attach_and_detach_state() -> None:
    ctrl = _make_controller(PhysicsTuning(grapple_enabled=True))
    ctrl.attach_grapple(anchor=LVector3f(5.0, 0.0, 2.0))
    assert ctrl.is_grapple_attached()
    ctrl.detach_grapple()
    assert not ctrl.is_grapple_attached()


def test_grapple_taut_rope_removes_outward_velocity() -> None:
    ctrl = _make_controller(PhysicsTuning(grapple_enabled=True))
    ctrl.pos = LVector3f(10.0, 0.0, 0.0)
    ctrl.vel = LVector3f(5.0, 0.0, 0.0)  # moving away from anchor
    ctrl.attach_grapple(anchor=LVector3f(0.0, 0.0, 0.0))
    ctrl._grapple_length = 8.0

    ctrl._apply_grapple_constraint(dt=0.016)
    assert ctrl.vel.x <= 0.0


def test_grapple_attach_boost_applies_velocity_toward_anchor() -> None:
    ctrl = _make_controller(PhysicsTuning(grapple_enabled=True, grapple_attach_boost=9.0))
    ctrl.pos = LVector3f(0.0, 0.0, 0.0)
    ctrl.vel = LVector3f(0.0, 0.0, 0.0)
    ctrl.attach_grapple(anchor=LVector3f(10.0, 0.0, 0.0))
    assert ctrl.vel.x > 8.5


def test_grapple_attach_auto_shortens_rope_for_configured_window() -> None:
    ctrl = _make_controller(
        PhysicsTuning(
            grapple_enabled=True,
            grapple_attach_boost=0.0,
            grapple_attach_shorten_speed=12.0,
            grapple_attach_shorten_time=0.20,
            grapple_min_length=1.0,
        )
    )
    ctrl.pos = LVector3f(0.0, 0.0, 0.0)
    ctrl.attach_grapple(anchor=LVector3f(20.0, 0.0, 0.0))
    start_len = ctrl._grapple_length

    ctrl._apply_grapple_constraint(dt=0.10)
    mid_len = ctrl._grapple_length
    ctrl._apply_grapple_constraint(dt=0.10)
    end_len = ctrl._grapple_length

    assert mid_len < start_len
    assert end_len < mid_len
