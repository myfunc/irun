from __future__ import annotations

import math

from panda3d.core import LVector3f

from ivan.physics.motion.config import derive_motion_config
from ivan.physics.motion.solver import MotionSolver
from ivan.physics.tuning import PhysicsTuning


def test_jump_derivation_uses_height_and_apex_time() -> None:
    tuning = PhysicsTuning(
        jump_height=2.0,
        jump_apex_time=0.5,
    )
    cfg = derive_motion_config(tuning=tuning)

    assert math.isclose(cfg.derived.gravity, 16.0, rel_tol=1e-6)
    assert math.isclose(cfg.derived.jump_takeoff_speed, 8.0, rel_tol=1e-6)


def test_exp_run_model_reaches_90_percent_at_t90() -> None:
    tuning = PhysicsTuning(
        run_t90=0.4,
        max_ground_speed=10.0,
    )
    solver = MotionSolver.from_tuning(tuning=tuning)
    vel = LVector3f(0.0, 0.0, 0.0)

    solver.apply_ground_run(vel=vel, wish_dir=LVector3f(1, 0, 0), dt=0.4, speed_scale=1.0)

    assert vel.x > 8.9
    assert vel.x < 9.1


def test_exp_run_model_converges_existing_overspeed_toward_vmax() -> None:
    tuning = PhysicsTuning(
        run_t90=0.4,
        max_ground_speed=6.0,
    )
    solver = MotionSolver.from_tuning(tuning=tuning)
    vel = LVector3f(11.0, 0.0, 0.0)

    solver.apply_ground_run(vel=vel, wish_dir=LVector3f(1, 0, 0), dt=0.2, speed_scale=1.0)

    assert vel.x < 10.0
    assert vel.x > 6.0


def test_ground_damping_reaches_10_percent_at_stop_t90() -> None:
    tuning = PhysicsTuning(
        ground_stop_t90=0.5,
    )
    solver = MotionSolver.from_tuning(tuning=tuning)
    vel = LVector3f(10.0, 0.0, 0.0)

    solver.apply_ground_coast_damping(vel=vel, dt=0.5)

    assert vel.x > 0.95
    assert vel.x < 1.05


def test_dash_speed_derived_from_distance_and_duration() -> None:
    tuning = PhysicsTuning(
        dash_distance=7.2,
        dash_duration=0.24,
    )
    cfg = derive_motion_config(tuning=tuning)

    assert math.isclose(cfg.derived.dash_speed, 30.0, rel_tol=1e-6)


def test_air_derivation_uses_speed_multiplier_and_t90() -> None:
    tuning = PhysicsTuning(
        max_ground_speed=8.0,
        air_speed_mult=1.5,
        air_gain_t90=0.30,
    )
    cfg = derive_motion_config(tuning=tuning)

    assert math.isclose(cfg.derived.air_speed, 12.0, rel_tol=1e-6)
    assert math.isclose(cfg.derived.air_accel, 3.0, rel_tol=1e-6)


def test_wallrun_sink_derivation_uses_jump_takeoff_and_t90() -> None:
    tuning = PhysicsTuning(
        jump_height=2.0,
        jump_apex_time=0.5,
        wallrun_sink_t90=0.20,
    )
    cfg = derive_motion_config(tuning=tuning)

    assert cfg.derived.wallrun_sink_speed < 0.0
    assert cfg.derived.wallrun_sink_k > 0.0
