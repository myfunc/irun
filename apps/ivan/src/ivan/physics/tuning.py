from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysicsTuning:
    gravity: float = 34.0
    jump_speed: float = 11.0
    max_ground_speed: float = 16.0
    max_air_speed: float = 18.0
    ground_accel: float = 72.0
    air_accel: float = 16.0
    friction: float = 6.5
    air_control: float = 0.35
    air_counter_strafe_brake: float = 38.0
    sprint_multiplier: float = 1.2
    mouse_sensitivity: float = 0.14
    wall_jump_boost: float = 10.0
    coyote_time: float = 0.12
    jump_buffer_time: float = 0.12
    enable_coyote: bool = True
    enable_jump_buffer: bool = True
    walljump_enabled: bool = True
    wallrun_enabled: bool = False
    vault_enabled: bool = False
    grapple_enabled: bool = False
    # Quake3-style character collision parameters.
    max_ground_slope_deg: float = 46.0
    step_height: float = 0.55
    ground_snap_dist: float = 0.20
    player_radius: float = 0.42
    player_half_height: float = 1.05
    player_eye_height: float = 0.65

