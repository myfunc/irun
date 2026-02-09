from __future__ import annotations

import math
from dataclasses import dataclass

from ivan.physics.tuning import PhysicsTuning


@dataclass(frozen=True)
class MotionInvariants:
    """Designer-facing motion invariants."""

    vmax: float
    run_t90: float
    ground_stop_t90: float
    jump_height: float
    jump_apex_time: float
    air_speed_mult: float
    air_gain_t90: float
    wallrun_sink_t90: float
    slide_stop_t90: float
    jump_buffer_time: float
    coyote_time: float


@dataclass(frozen=True)
class MotionDerived:
    """Runtime constants derived from invariants."""

    gravity: float
    jump_takeoff_speed: float
    run_exp_k: float
    ground_damp_k: float
    air_speed: float
    air_accel: float
    wallrun_sink_speed: float
    wallrun_sink_k: float
    slide_damp_k: float


@dataclass(frozen=True)
class MotionConfig:
    invariants: MotionInvariants
    derived: MotionDerived


def derive_motion_config(*, tuning: PhysicsTuning) -> MotionConfig:
    """
    Build a single movement config object from persisted tuning fields.

    The invariants remain designer-facing. Runtime uses only the derived constants.
    """

    vmax = max(0.01, float(tuning.max_ground_speed))
    run_t90 = max(1e-4, float(tuning.run_t90))
    ground_stop_t90 = max(1e-4, float(tuning.ground_stop_t90))

    jump_height = max(0.01, float(tuning.jump_height))
    jump_apex_time = max(1e-4, float(tuning.jump_apex_time))
    gravity = (2.0 * jump_height) / (jump_apex_time * jump_apex_time)
    jump_takeoff_speed = gravity * jump_apex_time
    run_exp_k = math.log(10.0) / run_t90
    ground_damp_k = math.log(10.0) / ground_stop_t90
    air_speed_mult = max(0.10, float(tuning.air_speed_mult))
    air_gain_t90 = max(1e-4, float(tuning.air_gain_t90))
    wallrun_sink_t90 = max(1e-4, float(tuning.wallrun_sink_t90))
    air_speed = vmax * air_speed_mult
    # Linear Quake-style accel term chosen so 0->90% of air speed is reached near T90.
    air_accel = 0.9 / air_gain_t90
    wallrun_sink_speed = -max(0.20, float(jump_takeoff_speed) * 0.12)
    wallrun_sink_k = math.log(10.0) / wallrun_sink_t90

    slide_stop_t90 = max(1e-4, float(tuning.slide_stop_t90))
    slide_damp_k = math.log(10.0) / slide_stop_t90

    invariants = MotionInvariants(
        vmax=vmax,
        run_t90=run_t90,
        ground_stop_t90=ground_stop_t90,
        jump_height=jump_height,
        jump_apex_time=jump_apex_time,
        air_speed_mult=air_speed_mult,
        air_gain_t90=air_gain_t90,
        wallrun_sink_t90=wallrun_sink_t90,
        slide_stop_t90=slide_stop_t90,
        jump_buffer_time=max(0.0, float(tuning.jump_buffer_time)),
        coyote_time=max(0.0, float(tuning.coyote_time)),
    )
    derived = MotionDerived(
        gravity=max(0.001, float(gravity)),
        jump_takeoff_speed=max(0.0, float(jump_takeoff_speed)),
        run_exp_k=max(0.0, float(run_exp_k)),
        ground_damp_k=max(0.0, float(ground_damp_k)),
        air_speed=max(0.0, float(air_speed)),
        air_accel=max(0.0, float(air_accel)),
        wallrun_sink_speed=float(wallrun_sink_speed),
        wallrun_sink_k=max(0.0, float(wallrun_sink_k)),
        slide_damp_k=max(0.0, float(slide_damp_k)),
    )
    return MotionConfig(invariants=invariants, derived=derived)
