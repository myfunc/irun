from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PhysicsTuning:
    # Invariant-driven movement core.
    # All primary run/jump/slide/ground-slowdown behavior derives from these timing/target values.
    run_t90: float = 0.240
    ground_stop_t90: float = 0.220
    jump_apex_time: float = 0.351
    slide_stop_t90: float = 3.000
    # Shared leniency window used by both jump buffer and coyote logic.
    grace_period: float = 0.120
    coyote_buffer_enabled: bool = True
    custom_friction_enabled: bool = True
    slide_enabled: bool = True
    harness_camera_smoothing_enabled: bool = True
    harness_animation_root_motion_enabled: bool = False
    camera_feedback_enabled: bool = True
    character_scale_lock_enabled: bool = False

    # Camera feel invariants (read-only observer; never writes gameplay velocity/state).
    camera_base_fov: float = 96.0
    camera_speed_fov_max_add: float = 9.0
    camera_tilt_gain: float = 1.0
    camera_event_gain: float = 1.0

    jump_height: float = 1.48
    max_ground_speed: float = 6.643
    # Air gain invariants.
    # `max_air_speed` and acceleration are derived from these two values.
    air_speed_mult: float = 1.695
    air_gain_t90: float = 0.240
    # Wallrun vertical sink response (lower is snappier sink control).
    wallrun_sink_t90: float = 0.220
    mouse_sensitivity: float = 0.14
    slide_half_height_mult: float = 0.68
    slide_eye_height_mult: float = 0.78
    wall_jump_boost: float = 5.534
    wall_jump_cooldown: float = 1.0
    surf_accel: float = 55.0
    surf_gravity_scale: float = 1.0
    surf_min_normal_z: float = 0.05
    surf_max_normal_z: float = 0.72
    vault_jump_multiplier: float = 1.25
    vault_height_boost: float = 0.10
    vault_forward_boost: float = 0.85
    vault_min_ledge_height: float = 0.20
    vault_max_ledge_height: float = 2.10
    vault_cooldown: float = 0.30
    autojump_enabled: bool = False
    noclip_enabled: bool = False
    noclip_speed: float = 9.0
    surf_enabled: bool = True
    walljump_enabled: bool = True
    wallrun_enabled: bool = False
    vault_enabled: bool = True
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
