from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysicsTuning:
    gravity: float = 24.0
    jump_height: float = 1.48
    max_ground_speed: float = 6.643
    max_air_speed: float = 11.258
    ground_accel: float = 26.340
    jump_accel: float = 1.000
    friction: float = 6.5
    air_control: float = 0.241
    air_counter_strafe_brake: float = 23.0
    mouse_sensitivity: float = 0.14
    crouch_speed_multiplier: float = 0.65
    crouch_half_height: float = 0.68
    crouch_eye_height: float = 0.42
    wall_jump_boost: float = 5.534
    wall_jump_cooldown: float = 1.0
    surf_accel: float = 55.0
    surf_gravity_scale: float = 1.0
    surf_min_normal_z: float = 0.05
    surf_max_normal_z: float = 0.72
    vault_jump_multiplier: float = 1.25
    vault_forward_boost: float = 2.0
    vault_min_ledge_height: float = 0.20
    vault_max_ledge_height: float = 1.40
    vault_cooldown: float = 0.30
    jump_buffer_time: float = 0.14
    enable_jump_buffer: bool = True
    autojump_enabled: bool = False
    noclip_enabled: bool = False
    noclip_speed: float = 9.0
    surf_enabled: bool = True
    walljump_enabled: bool = True
    wallrun_enabled: bool = False
    vault_enabled: bool = False
    crouch_enabled: bool = True
    grapple_enabled: bool = False
    grapple_fire_range: float = 180.0
    grapple_attach_boost: float = 8.0
    grapple_attach_shorten_speed: float = 20.0
    grapple_attach_shorten_time: float = 0.20
    grapple_pull_strength: float = 60.0
    grapple_min_length: float = 1.2
    grapple_max_length: float = 150.0
    grapple_rope_half_width: float = 0.028
    # Quake3-style character collision parameters.
    max_ground_slope_deg: float = 46.0
    step_height: float = 0.55
    ground_snap_dist: float = 0.056
    player_radius: float = 0.42
    player_half_height: float = 1.05
    player_eye_height: float = 0.625

    # Time-trial course marker placement (F5/F6): half extents for the AABB volumes.
    course_marker_half_extent_xy: float = 2.5
    course_marker_half_extent_z: float = 2.0

    # Rendering / visibility debugging (default OFF: avoid artifacts on GoldSrc PVS maps).
    vis_culling_enabled: bool = False
