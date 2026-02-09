# Movement Debug Surface Reduction (Invariant-First)

## Why
Movement tuning drifted into over-coupled scalar editing:
- changing one value (speed/jump/gravity/air accel) forced retuning many others.
- debug menu had too many overlapping controls to reason about quickly.

## Decision (Current Pass)
Runtime debug tuning is now intentionally compact and invariant-first.

Kept controls:
- `max_ground_speed` (`Vmax`)
- `run_t90`
- `ground_stop_t90`
- `air_speed_mult`
- `air_gain_t90`
- `wallrun_sink_t90`
- `jump_height`
- `jump_apex_time`
- `jump_buffer_time`
- `coyote_time`
- `slide_stop_t90`

Kept toggles:
- `autojump_enabled`
- `coyote_buffer_enabled`
- `custom_friction_enabled`
- `slide_enabled`
- `wallrun_enabled`
- `surf_enabled`
- `harness_camera_smoothing_enabled`
- `harness_animation_root_motion_enabled`

Not exposed anymore in debug UI:
- legacy direct movement scalars and many niche feature sliders.
- legacy air-gain scalars (`max_air_speed`, `jump_accel`, `air_control`, `air_counter_strafe_brake`) are now migration-only fields.

## Migration Notes
- default profiles are migrated to invariant timing params to preserve baseline behavior as much as possible.
- legacy direct run/gravity tuning fields are mapped to invariant timing fields (`run_t90`, `ground_stop_t90`, `jump_apex_time`) then removed from active tuning data.
- legacy air scalars are mapped to two air invariants:
  - `air_speed_mult = legacy_max_air_speed / max_ground_speed`
  - `air_gain_t90 = 0.9 / legacy_jump_accel`

## Slide policy addendum
- Slide is hold-based (`Shift` down = active, release = exit).
- Slide must preserve carried horizontal speed on engage (no artificial entry boost).
- Slide deceleration is controlled only by `slide_stop_t90` so it stays independent from normal ground stop tuning.
- Slide steering should be camera-yaw driven; keyboard strafe should not directly steer slide.

## Risks
- hidden advanced settings still exist in profile/state payloads; accidental edits outside debug UI can still affect behavior.
- surf still uses legacy internals in parts; surf scalar tuning is intentionally hidden for now to keep debug surface focused on invariants.
- if consumed ground-jump ticks still run ground decel/clamp, bhop carry speed gets destroyed on landing frames.

## Next
- complete state-machine authority split so non-solver velocity writes are impossible.
- add deterministic replay state hashes for direct “same input, same output” verification.
- once animator/root-motion layer is real, keep it read-only and measurable via harness toggles.
