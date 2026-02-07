from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysicsTuning:
    gravity: float = 24.0
    jump_height: float = 1.48
    max_ground_speed: float = 8.976
    max_air_speed: float = 11.258
    ground_accel: float = 48.009
    jump_accel: float = 11.408
    friction: float = 6.5
    air_control: float = 0.35
    air_counter_strafe_brake: float = 5.0
    mouse_sensitivity: float = 0.14
    wall_jump_boost: float = 5.534
    vault_jump_multiplier: float = 1.25
    vault_forward_boost: float = 2.0
    vault_min_ledge_height: float = 0.20
    vault_max_ledge_height: float = 1.40
    vault_cooldown: float = 0.30
    coyote_time: float = 0.12
    jump_buffer_time: float = 0.14
    enable_coyote: bool = True
    enable_jump_buffer: bool = True
    walljump_enabled: bool = False
    wallrun_enabled: bool = True
    vault_enabled: bool = False
    grapple_enabled: bool = False
    # Quake3-style character collision parameters.
    max_ground_slope_deg: float = 46.0
    step_height: float = 0.55
    ground_snap_dist: float = 0.056
    player_radius: float = 0.42
    player_half_height: float = 1.05
    player_eye_height: float = 0.625
