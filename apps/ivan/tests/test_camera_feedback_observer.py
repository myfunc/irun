from __future__ import annotations

from panda3d.core import LVector3f

from ivan.game.camera_feedback_observer import CameraFeedbackObserver


def _observe(
    obs: CameraFeedbackObserver,
    *,
    dt: float,
    horizontal_speed: float,
    enabled: bool = True,
    base_fov: float = 96.0,
    speed_max_add: float = 9.0,
    event_gain: float = 1.0,
):
    return obs.observe(
        dt=dt,
        horizontal_speed=horizontal_speed,
        max_ground_speed=6.0,
        enabled=enabled,
        base_fov_deg=base_fov,
        speed_fov_max_add_deg=speed_max_add,
        event_gain=event_gain,
    )


def test_speed_fov_increases_with_horizontal_speed() -> None:
    obs = CameraFeedbackObserver()
    pose_idle = _observe(obs, dt=0.0, horizontal_speed=0.0, speed_max_add=12.0, event_gain=0.0)
    pose_fast = _observe(obs, dt=0.016, horizontal_speed=12.0, speed_max_add=12.0, event_gain=0.0)
    assert pose_fast.fov_deg > pose_idle.fov_deg


def test_speed_fov_does_not_change_until_above_vmax() -> None:
    obs = CameraFeedbackObserver()
    pose_at_vmax = obs.observe(
        dt=0.0,
        horizontal_speed=6.0,
        max_ground_speed=6.0,
        enabled=True,
        base_fov_deg=96.0,
        speed_fov_max_add_deg=12.0,
        event_gain=0.0,
    )
    pose_below = obs.observe(
        dt=0.016,
        horizontal_speed=5.5,
        max_ground_speed=6.0,
        enabled=True,
        base_fov_deg=96.0,
        speed_fov_max_add_deg=12.0,
        event_gain=0.0,
    )
    assert pose_at_vmax.fov_deg == 96.0
    assert pose_below.fov_deg == 96.0


def test_speed_fov_caps_at_base_plus_gain_by_10x_vmax() -> None:
    obs_10x = CameraFeedbackObserver()
    pose_10x = obs_10x.observe(
        dt=0.0,
        horizontal_speed=60.0,
        max_ground_speed=6.0,
        enabled=True,
        base_fov_deg=92.0,
        speed_fov_max_add_deg=14.0,
        event_gain=0.0,
    )
    obs_above = CameraFeedbackObserver()
    pose_above = obs_above.observe(
        dt=0.0,
        horizontal_speed=200.0,
        max_ground_speed=6.0,
        enabled=True,
        base_fov_deg=92.0,
        speed_fov_max_add_deg=14.0,
        event_gain=0.0,
    )
    assert pose_10x.fov_deg == 106.0
    assert pose_above.fov_deg == 106.0


def test_speed_fov_response_is_visible_in_common_high_speed_range() -> None:
    obs = CameraFeedbackObserver()
    pose = obs.observe(
        dt=0.0,
        horizontal_speed=24.0,  # ~4x Vmax for Vmax=6
        max_ground_speed=6.0,
        enabled=True,
        base_fov_deg=94.0,
        speed_fov_max_add_deg=25.0,
        event_gain=0.0,
    )
    # Ensure practical high-speed runs produce a clearly visible widening.
    assert pose.fov_deg >= 106.0
    assert pose.speed_t >= 0.45


def test_landing_event_produces_pitch_impulse_and_decay() -> None:
    obs = CameraFeedbackObserver()
    obs.record_sim_tick(
        now=1.0,
        jump_pressed=False,
        jump_held=False,
        autojump_enabled=False,
        grace_period=0.12,
        max_ground_speed=6.0,
        pre_grounded=False,
        post_grounded=True,
        pre_vel=LVector3f(0.0, 0.0, -8.0),
        post_vel=LVector3f(0.0, 0.0, 0.0),
    )
    pose_now = _observe(obs, dt=0.016, horizontal_speed=0.0, speed_max_add=0.0, event_gain=1.0)
    assert pose_now.pitch_deg < -0.1
    assert pose_now.event_name == "landing"
    assert pose_now.event_quality > 0.1

    pose_later = pose_now
    for _ in range(40):
        pose_later = _observe(obs, dt=0.016, horizontal_speed=0.0, speed_max_add=0.0, event_gain=1.0)
    assert pose_later.pitch_deg > pose_now.pitch_deg


def test_successful_bhop_takeoff_triggers_short_fov_pulse() -> None:
    obs = CameraFeedbackObserver()
    obs.record_sim_tick(
        now=2.00,
        jump_pressed=False,
        jump_held=False,
        autojump_enabled=False,
        grace_period=0.12,
        max_ground_speed=6.0,
        pre_grounded=False,
        post_grounded=True,
        pre_vel=LVector3f(0.0, 0.0, -3.0),
        post_vel=LVector3f(0.0, 0.0, 0.0),
    )
    obs.record_sim_tick(
        now=2.04,
        jump_pressed=True,
        jump_held=False,
        autojump_enabled=False,
        grace_period=0.12,
        max_ground_speed=6.0,
        pre_grounded=True,
        post_grounded=False,
        pre_vel=LVector3f(6.0, 0.0, 0.0),
        post_vel=LVector3f(6.0, 0.0, 4.2),
    )

    pose = _observe(obs, dt=0.016, horizontal_speed=0.0, speed_max_add=0.0, event_gain=1.2)
    assert pose.fov_deg > 96.0
    assert pose.event_name == "bhop"
    assert pose.event_quality > 0.1


def test_feedback_disabled_returns_base_fov_and_zero_offsets() -> None:
    obs = CameraFeedbackObserver()
    pose = _observe(obs, dt=0.016, horizontal_speed=20.0, enabled=False, base_fov=93.0, speed_max_add=20.0, event_gain=2.0)
    assert pose.fov_deg == 93.0
    assert pose.pitch_deg == 0.0
    assert pose.roll_deg == 0.0
    assert pose.event_name == "none"


def test_bhop_blocked_reason_reports_timing_failure() -> None:
    obs = CameraFeedbackObserver()
    obs.record_sim_tick(
        now=4.0,
        jump_pressed=False,
        jump_held=False,
        autojump_enabled=False,
        grace_period=0.12,
        max_ground_speed=6.0,
        pre_grounded=True,
        post_grounded=False,
        pre_vel=LVector3f(5.0, 0.0, 0.0),
        post_vel=LVector3f(5.0, 0.0, 4.0),
    )
    pose = _observe(obs, dt=0.016, horizontal_speed=5.0, speed_max_add=0.0, event_gain=1.0)
    assert pose.event_blocked_reason == "bhop_timing"
